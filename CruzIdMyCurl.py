import socket
import argparse


LOG_CSV_COLUMNS = [
    'Successful or Unsuccessful',
    'Requested URL' ,
    'Hostname',
    'source IP',
    'destination IP',
    'source port',
    'destination port',
    'Server Response line'
]


class AppException(Exception):
    pass


class HttpGet:
    ENCODING = 'iso-8859-1'

    def __init__(self, url: str, hostname=None) -> None:
        self.response_data = b''
        self.url = url
        self.hostname = hostname
        self.fp = None

    def parse_url(self) -> tuple:
        scheme_url = self.url.split('://')

        if len(scheme_url) != 2:
            raise AppException('Invalid url.')

        port = 80

        try:
            host_with_port, resource_path = scheme_url[1].split('/', 1)
        except ValueError:
            host_with_port = scheme_url[1].split('/', 1)[0]
            resource_path = '/'

        resource_path = resource_path if resource_path == '/' else '/' + resource_path
        host_with_port = host_with_port.split(':', 1)

        if len(host_with_port) == 2:
            port = int(host_with_port[1])

        return scheme_url[0], host_with_port[0], resource_path, port

    def prepare_request_str(self, hostname: str, resource_path: str) -> str:
        return 'GET {} HTTP/1.1\r\nHost:{}\r\n\r\n'.format(resource_path, hostname).encode()

    def read_status_line(self) -> tuple:
        status_line = self.fp.readline()

        if not status_line:
            return None, None

        self.response_data += status_line
        status_line = status_line.decode(self.ENCODING)
        try:
            _, status, reason = status_line.split(None, 2)
        except ValueError:
            try:
                _, status = status_line.split(None, 1)
            except ValueError:
                status = None

            reason = ''

        return status, reason

    def read_header(self) -> dict:
        headers = {}
        while True:
            line = self.fp.readline()
            self.response_data += line

            if line in (b'\r\n', b'\n', b''):
                break

            line = line.decode(self.ENCODING).replace('\r\n', '')
            key, value = line.split(': ', 1)
            headers[str(key).lower()] = value

        return headers

    def read_content(self, content_length: int) -> bytes:
        s = []
        while content_length > 0:
            chunk = self.fp.read(min(content_length, 1048576))

            if not chunk:
                pass

            s.append(chunk)
            content_length -= len(chunk)

        return b"".join(s)

    def receive(self, client: socket.socket) -> dict:
        response = {
            'content': b'',
            'chunked': False,
            'status': None,
            'reason': None,
            'content-encoding': None
        }
        self.fp = client.makefile('rb')
        status, reason = self.read_status_line()

        if not status:
            return response

        response.update({
            'status': status,
            'reason': reason,
        })
        header = self.read_header()

        if header.get('transfer-encoding', '').lower() == 'chunked':
            response.update({
                'chunked': True
            })
            return response

        try:
            content_length = int(header.get('content-length'))
        except ValueError:
            content_length = 0

        response.update({
            'content': self.read_content(content_length),
            'content-encoding': header.get('content-encoding')
        })
        self.fp.close()

        return response

    @staticmethod
    def log_message(status, url: str, host: str, source_ip: str, destination_ip: str,
                    source_port: str, destination_port: str, respons_line: str) -> None:
        with open('LOG.csv', 'a+') as f:
            f.seek(0)
            char = f.read(1)

            if not char:
                f.write(','.join(LOG_CSV_COLUMNS) + '\n')

            f.seek(0, 2)
            f.write('{},{},{},{},{},{},{},{}\n'.format(
                status, url, host, source_ip, destination_ip, source_port, destination_port, respons_line
            ))

    @staticmethod
    def is_ip(host: str) -> bool:
        try:
            socket.inet_aton(host)
        except socket.error:
            return False

        return True

    @staticmethod
    def stdout_response_status(status, url: str, resposne_header: str) -> None:
        print('{} {} {}'.format(status, url, resposne_header))

    def get_destination_ip_and_host_name(self, host: str, hostname: str):
        host_is_ip = self.is_ip(host)

        if not hostname and host_is_ip:
            raise AppException('Please provide a hostname.')

        if not host_is_ip:
            hostname = host
            try:
                destination_ip = socket.gethostbyname(hostname)
            except socket.error:
                raise AppException('Could not resolve host.')

        else:
            destination_ip = host

        return destination_ip, hostname

    def get(self, client: socket.socket, host: str, hostname: str, resource_path: str, destination_port: int) -> dict:
        client.connect((host, destination_port))
        client.sendall(self.prepare_request_str(hostname, resource_path))

        return self.receive(client)

    def make_request(self) -> None:
        scheme, host, resource_path, destination_port = self.parse_url()

        if scheme.lower() == 'https':
            raise AppException('HTTPS is not supported.')

        destination_ip, self.hostname = self.get_destination_ip_and_host_name(host, self.hostname)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            response = self.get(client, host, self.hostname, resource_path, destination_port)
            source_ip, source_port = client.getsockname()

        decoded_response = self.response_data.decode(self.ENCODING)

        if not self.response_data:
            self.stdout_response_status('Unsuccessful', self.url, 'Empty reply from server.')
            self.log_message(
                'Unsuccessful', self.url, self.hostname, source_ip, destination_ip,
                source_port, destination_port, 'Empty reply from server.'
            )
            return

        if response['chunked']:
            self.log_message(
                'Unsuccessful', self.url, self.hostname, source_ip, destination_ip,
                source_port, destination_port, self.response_data
            )
            print('Chunked transfer encoding is not supported.')
            return

        if not response['content']:
            self.stdout_response_status('Unsuccessful', self.url, decoded_response)
            self.log_message(
                'Unsuccessful', self.url, self.hostname, source_ip, destination_ip,
                source_port, destination_port, self.response_data
            )
            return

        if response['status'] and response['content']:
            with open('HTTPoutput.html', 'w', encoding=self.ENCODING) as f:
                f.writelines(response['content'].decode(self.ENCODING))

            self.stdout_response_status('Success', self.url, decoded_response)
            self.log_message(
                'Successful', self.url, self.hostname, source_ip, destination_ip,
                source_port, destination_port, self.response_data
            )
            return

        self.stdout_response_status('Unsuccessful', self.url, decoded_response)
        self.log_message(
            'Unsuccessful', self.url, self.hostname, source_ip, destination_ip,
            source_port, destination_port, self.response_data
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('hostname', nargs='?')
    args = parser.parse_args()
    http_get = HttpGet(args.url, args.hostname)

    try:
        http_get.make_request()
    except socket.timeout:
        print('Failed to receive data from socket: Timed out')
    except TimeoutError:
        print('Failed to connect to {}: Timed out'.format(args.url))
    except AppException as e:
        print(e)
    finally:
        if http_get.fp and not http_get.fp.closed: http_get.fp.close()
