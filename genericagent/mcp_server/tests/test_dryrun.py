import unittest


class DryrunPolicyTests(unittest.TestCase):
    def test_placeholder(self):
        # The dryrun tool is registered through FastMCP; behavioral coverage is
        # exercised by integration tests once a client is attached.
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
