import socket
import argparse


class HttpGet:
    def __init__(self, url, hostname=None) -> None:
        self.response_data = b''
        self.url = url
        self.hostname = hostname
        self.fp = None

    def parts_of_url(self):
        scheme_and_url = self.url.split('://')

        if len(scheme_and_url) != 2:
            raise Exception('Invalid url.')

        port = 80

        try:
            host_with_port, resource_path = scheme_and_url[1].split('/', 1)
        except ValueError:
            host_with_port = scheme_and_url[1].split('/', 1)[0]
            resource_path = '/'

        resource_path = resource_path if resource_path == '/' else '/' + resource_path
        host_with_port = host_with_port.split(':', 1)

        if len(host_with_port) == 2:
            port = int(host_with_port[1])

        return scheme_and_url[0], host_with_port[0], resource_path, port

    def get_request_str(self, hostname, resource_path):
        request_str = 'GET {} HTTP/1.1\r\nHost:{}\r\n\r\n'.format(resource_path, hostname).encode()

        return request_str

    def read_status_line(self):
        status_line = self.fp.readline()

        if not status_line:
            return None, None

        self.response_data = self.response_data + status_line
        status_line = status_line.decode('iso-8859-1')
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
            self.response_data = self.response_data + line

            if line == b'\r\n':
                break

            if line == b'\n':
                break

            if line == b'':
                break

            line = line.decode('iso-8859-1').replace('\r\n', '')
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
                LOG_CSV_COLUMNS = 'Successful or Unsuccessful,Requested URL,Hostname,source IP,destination IP,source port,destination port,Server Response line\n'
                f.write(LOG_CSV_COLUMNS)

            f.seek(0, 2)
            f.write('{},{},{},{},{},{},{},{}\n'.format(
                status, url, host, source_ip, destination_ip, source_port, destination_port, respons_line
            ))

    @staticmethod
    def is_ip(host):
        try:
            socket.inet_aton(host)
        except socket.error:
            return False

        return True

    @staticmethod
    def stdout_response_status(status, url, resposne_header):
        print('{} {} {}'.format(status, url, resposne_header))

    def get_destination_ip_and_host_name(self, host, hostname):
        host_is_ip = self.is_ip(host)

        if not hostname and host_is_ip:
            raise Exception('Please provide a hostname.')

        if not host_is_ip:
            hostname = host
            try:
                destination_ip = socket.gethostbyname(hostname)
            except socket.error:
                raise Exception('Could not resolve host.')

        else:
            destination_ip = host

        return destination_ip, hostname

    def get_data_from_desitination(self, client, host, hostname, resource_path, destination_port):
        client.connect((host, destination_port))
        client.sendall(self.get_request_str(hostname, resource_path))

        return self.receive(client)

    def make_request(self):
        scheme, host, resource_path, destination_port = self.parts_of_url()

        if scheme.lower() == 'https':
            raise Exception('HTTPS is not supported.')

        destination_ip, self.hostname = self.get_destination_ip_and_host_name(host, self.hostname)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            response = self.get_data_from_desitination(client, host, self.hostname, resource_path, destination_port)
            source_ip, source_port = client.getsockname()
        except Exception as e:
            print(e)
            raise Exception('Unexpected error')
        finally:
            client.close()  # Closing TCP connection.

        decoded_response = self.response_data.decode('iso-8859-1')

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
            with open('HTTPoutput.html', 'w', encoding='iso-8859-1') as f:
                f.writelines(response['content'].decode('iso-8859-1'))

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
    except Exception as e:
        print(e)
    finally:
        if http_get.fp and not http_get.fp.closed: http_get.fp.close()
