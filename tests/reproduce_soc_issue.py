import time
import unittest
from utils.soc_filter import SOCFilter

class TestSOCFilterReproduction(unittest.TestCase):
    def test_rapid_toggle_rejection(self):
        """Reproduce the rejection of 90->89->90 in rapid succession"""
        f = SOCFilter("test_device")
        
        # Initial reading
        t0 = 1000.0
        self.assertEqual(f.filter(90.0, t0), 90.0)
        
        # Rapid update 1: 89% after 0.1s
        # Expected: Currently REJECTED (returns None) due to rate limit
        t1 = t0 + 0.1
        res1 = f.filter(89.0, t1)
        print(f"90->89 in 0.1s: {res1}")
        
        # Rapid update 2: 90% after another 0.1s
        t2 = t1 + 0.1
        res2 = f.filter(90.0, t2)
        print(f"89->90 in 0.1s: {res2}")
        
        # Assert that now it PASSES (returns a value)
        # Because the change is small (1%), it should be considered plausible
        self.assertIsNotNone(res1, "Small 1% change should be accepted")
        self.assertIsNotNone(res2, "Small 1% return change should be accepted")
        
if __name__ == "__main__":
    unittest.main()
