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
RESPONSE_DATA = b""


def parse_url(url: str):
    scheme_url = url.split('://')

    if len(scheme_url) != 2:
        print('Invalid url.')
        exit()

    port = 80
    colon_splitted_url = scheme_url[1].split(':')

    if len(colon_splitted_url) == 2:
        port = int(colon_splitted_url[1])

    url_path = colon_splitted_url[0].split('/')
    host = url_path[0]
    resource_path = '/' +  '/'.join(url_path[1:])

    return scheme_url[0], host, resource_path, port


def prepare_request(host_name, resource_path):
    return 'GET {} HTTP/1.1\r\nHost:{}\r\n\r\n'.format(resource_path, host_name).encode()


def read_status_line(fp):
    global RESPONSE_DATA
    status_line = fp.readline()

    if not status_line:
        return None, None

    RESPONSE_DATA += status_line
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


def read_header(fp):
    global RESPONSE_DATA
    headers = {}
    while True:
        line = fp.readline()
        # RESPONSE_DATA += line

        if line in (b'\r\n', b'\n', b''):
            break

        line = line.decode('iso-8859-1').replace('\r\n', '')
        key, value = line.split(': ', 1)
        headers[str(key).lower()] = value

    return headers


def read_content(fp, content_length):
    s = []
    while content_length > 0:
        chunk = fp.read(min(content_length, 1048576))

        if not chunk:
            pass

        s.append(chunk)
        content_length -= len(chunk)

    return b"".join(s)

def receive(client):
    response = {
        'content': b'',
        'chunked': False,
        'status': None,
        'reason': None,
        'content-encoding': None
    }
    fp = client.makefile('rb')
    status, reason = read_status_line(fp)

    if not status:
        return response

    response.update({
        'status': status,
        'reason': reason,
    })
    header = read_header(fp)

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
        'content': read_content(fp, content_length),
        'content-encoding': header.get('content-encoding')
    })
    fp.close()

    return response


def log_message(status, url, host, source_ip, destination_ip, source_port, destination_port, respons_line):
    with open('LOG.csv', 'a+') as f:
        char = f.read(1)

        if not char:
            f.write(','.join(LOG_CSV_COLUMNS) + '\n')

        f.write('{},{},{},{},{},{},{},{}'.format(
            status, url, host, source_ip, destination_ip, source_port, destination_port, respons_line
        ))


def is_ip(host):
    try:
        socket.inet_aton(host)
    except Exception:
        return False

    return True


def stdout_response_status(status, url, resposne_header):
    print('{} {} {}'.format(status, url, resposne_header))


def get_destination_ip_and_host_name(host, hostname):
    host_is_ip = is_ip(host)

    if not hostname and host_is_ip:
        print('Please provide a hostname.')
        exit()

    if not host_is_ip:
        hostname = host
        try:
            destination_ip = socket.gethostbyname(hostname)
        except Exception:
            print('Could not resolve host.')
            exit()
    else:
        destination_ip = host

    return destination_ip, hostname


def get(client, host, hostname, resource_path, destination_port):
    client.connect((host, destination_port))
    client.sendall(prepare_request(hostname, resource_path))

    return receive(client)

# 'http://wholemajestictranscendentkiss.neverssl.com/online' 200
# https://facebook.com 301
# https://facebook.com:443
# http://www.debuggerstepthrough.com/feeds/posts/default  chunked

def main(url: str, hostname=None):
    global RESPONSE_DATA
    scheme, host, resource_path, destination_port = parse_url(url)

    if scheme.lower() == 'https':
        print('HTTPS is not supported.')
        exit()

    destination_ip, hostname = get_destination_ip_and_host_name(host, hostname)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        response = get(client, host, hostname, resource_path, destination_port)
        source_ip, source_port = client.getsockname()

    decoded_response = RESPONSE_DATA.decode('iso-8859-1')

    if not RESPONSE_DATA:
        stdout_response_status('Unsuccessful', url, 'error: Empty response')
        log_message(
            'Unsuccessful', url, hostname, source_ip, destination_ip,
            source_port, destination_port, 'error: Empty response'
        )
        return

    if response['chunked']:
        log_message(
            'Unsuccessful', url, hostname, source_ip, destination_ip,
            source_port, destination_port, RESPONSE_DATA
        )
        print('Chunked transfer encoding is not supported.')
        return

    if not response['content']:
        stdout_response_status('Unsuccessful', url, decoded_response)
        log_message(
            'Unsuccessful', url, hostname, source_ip, destination_ip,
            source_port, destination_port, RESPONSE_DATA
        )
        return

    if response['status']:
        with open('HTTPoutput.html', 'w', encoding='iso-8859-1') as f:
            f.writelines(response['content'].decode('iso-8859-1'))

    if response['status'] == '200':
        stdout_response_status('Success', url, decoded_response)
        log_message(
            'Successful', url, hostname, source_ip, destination_ip,
            source_port, destination_port, RESPONSE_DATA
        )
        return

    stdout_response_status('Unsuccessful', url, decoded_response)
    log_message(
        'Unsuccessful', url, hostname, source_ip, destination_ip,
        source_port, destination_port, RESPONSE_DATA
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('hostname', nargs='?')
    args = parser.parse_args()

    try:
        main(args.url, args.hostname)
    except socket.timeout:
        print(f'Failed to connect to {args.url}: Timed out')
    except Exception as e:
        print('{}'.format(e))
