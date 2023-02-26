import time

import pyjs8call

import test_cross_platform


tests = [
    test_cross_platform
]


def test_run(test_module):
    passed = False
    exceptions = []

    print('-------------------------')
    print('Test: ' + test_module.NAME)
    print('')

    start = time.time()

#    try:
    passed = test_module.run()
#    except Exception as e:
#        exceptions.append(e)

    end = time.time()

    if len(exceptions) == 0 and passed:
        status = 'PASSED'
#    elif len(exceptions) > 0:
#        status = 'FAILED'
#
#        print('Exceptions:')
#        for e in exceptions:
#            print('\t' + type(e).__name__ + ': '  + str(e))
    else:
        status = 'FAILED'

    print('')
    print('Status: ' + status)
    print('Duration: ' + test_duration(start, end))
    print('-------------------------')
    
def test_duration(start, end):
    duration = end - start

    if duration < 0.001:
        duration = round(duration * 1000000, 3)
        units = 'us'
    elif duration < 1:
        duration = round(duration * 1000, 3)
        units = 'ms'
    else:
        duration = round(duration, 3)
        units = 's'

    return str(duration) + ' ' + units


for test in tests:
    test_run(test)

