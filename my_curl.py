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

    def __init__(self, url, hostname=None) -> None:
        self.response_data = b''
        self.url = url
        self.hostname = hostname
        self.fp = None

    def parse_url(self):
        scheme_url = self.url.split('://')

        if len(scheme_url) != 2:
            raise AppException('Invalid url.')

        port = 80
        colon_splitted_url = scheme_url[1].split(':')

        if len(colon_splitted_url) == 2:
            port = int(colon_splitted_url[1])

        url_path = colon_splitted_url[0].split('/')
        host = url_path[0]
        resource_path = '/' +  '/'.join(url_path[1:])

        return scheme_url[0], host, resource_path, port


    def prepare_request(self, host_name, resource_path):
        return 'GET {} HTTP/1.1\r\nHost:{}\r\n\r\n'.format(resource_path, host_name).encode()

    def read_status_line(self):
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


    def read_header(self):
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


    def read_content(self, content_length):
        s = []
        while content_length > 0:
            chunk = self.fp.read(min(content_length, 1048576))

            if not chunk:
                pass

            s.append(chunk)
            content_length -= len(chunk)

        return b"".join(s)


    def receive(self, client):
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
    def log_message(status, url, host, source_ip, destination_ip, source_port, destination_port, respons_line):
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
    def is_ip(host):
        try:
            socket.inet_aton(host)
        except Exception:
            return False

        return True

    @staticmethod
    def stdout_response_status(status, url, resposne_header):
        print('{} {} {}'.format(status, url, resposne_header))

    def get_destination_ip_and_host_name(self, host, hostname):
        host_is_ip = self.is_ip(host)

        if not hostname and host_is_ip:
            raise AppException('Please provide a hostname.')

        if not host_is_ip:
            hostname = host
            try:
                destination_ip = socket.gethostbyname(hostname)
            except Exception:
                raise AppException('Could not resolve host.')

        else:
            destination_ip = host

        return destination_ip, hostname

    def get(self, client, host, hostname, resource_path, destination_port):
        client.connect((host, destination_port))
        client.sendall(self.prepare_request(hostname, resource_path))

        return self.receive(client)

    # 'http://wholemajestictranscendentkiss.neverssl.com/online' 200
    # https://facebook.com 301
    # https://facebook.com:443
    # http://www.debuggerstepthrough.com/feeds/posts/default  chunked

    def make_request(self):
        scheme, host, resource_path, destination_port = self.parse_url()

        if scheme.lower() == 'https':
            raise AppException('HTTPS is not supported.')

        destination_ip, self.hostname = self.get_destination_ip_and_host_name(host, self.hostname)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            response = self.get(client, host, self.hostname, resource_path, destination_port)
            source_ip, source_port = client.getsockname()

        decoded_response = self.response_data.decode(self.ENCODING)

        if not self.response_data:
            self.stdout_response_status('Unsuccessful', self.url, 'error: Empty response')
            self.log_message(
                'Unsuccessful', self.url, self.hostname, source_ip, destination_ip,
                source_port, destination_port, 'error: Empty response'
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
        print(f'Failed to connect to {args.url}: Timed out')
    except Exception as e:
        print('{}'.format(e))
    finally:
        if http_get.fp and not http_get.fp.closed: http_get.fp.close()
