import requests
r = requests.get('http://localhost:8000/analytics/overview?period=30d')
print('STATUS', r.status_code)
print('CONTENT-TYPE', r.headers.get('content-type'))
print('BODY REPR:', repr(r.text)[:2000])
print('\nFULL BODY:\n', r.text)
