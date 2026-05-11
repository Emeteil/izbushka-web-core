from com_link_rt import ComLinkConnection, PingCommand, MillisCommand
from collections import deque
import time
import sys

def main():
    with ComLinkConnection('COM4', timeout=0) as conn:
        print("connect()\n")

        ping = PingCommand(conn)

        results = deque(maxlen=250)

        print("Cur:\t")
        print("Max:\t")
        print("Min:\t")
        print("Avr:\t")

        try:
            while True:
                response_time = ping.execute()
                if response_time:
                    results.append(response_time)
    
                current_max = max(results)
                current_min = min(results)
                current_avg = sum(results) / len(results)
    
                sys.stdout.write("\033[4F")
    
                print(f"Cur:\t{(response_time or float('inf')):7.3f} ms")
                print(f"Max:\t{current_max:7.3f} ms")
                print(f"Min:\t{current_min:7.3f} ms")
                print(f"Avr:\t{current_avg:7.3f} ms")
    
                sys.stdout.flush()
        except (Exception, KeyboardInterrupt):
            sys.stdout.flush()
        finally:
            print("\ndisconnect()")

if __name__ == "__main__":
    main()