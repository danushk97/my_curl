It is a python script which helps transfer and receive data to and from other servers using HTTP protocol.

Note: It is capable of performing only HTTP GET.


Prerequisites
-------------
    - python 3


Run the script
--------------
    - open cmd prompt
    - navigate to location where MyCruzIdMyCurl.py is present
    - run python3 MyCruzIdMyCurl.py <cmd_line_arg_1> <cmd_line_arg_2>

        cmd_line_arg_1:
            required: true
            expected_value: URL

        cmd_line_arg_2:
            required: true when the URL, i.e, value of cmd_line_arg_1, uses IP address at the place of host.
                      For example when the URL is http://120.12.3.4/foo
            expected_value: Host name.


Output
------
    - The response content of the last executed command will be in the file called HTTPoutput.html.
    It will be located in directory from where the command is executed.
    - The logs will be captured in a file called LOG.csv and it will be in the same location as
    HTTPoutput.html
