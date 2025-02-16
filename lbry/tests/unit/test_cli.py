import contextlib
import logging
from io import StringIO
from unittest import TestCase

import docopt
from torba.testcase import AsyncioTestCase

from lbry.extras.cli import normalize_value, main, setup_logging
from lbry.extras.system_info import get_platform
from lbry.extras.daemon.Daemon import Daemon
from lbry.conf import Config
from lbry.extras import cli


class CLILoggingTest(AsyncioTestCase):

    async def test_setup_logging(self):
        # test needs to be async to avoid warnings from loggly

        def setup(argv):
            parser = cli.get_argument_parser()
            args, command_args = parser.parse_known_args(argv)
            conf = Config.create_from_arguments(args)
            conf.data_dir = '/tmp'
            setup_logging(args, conf, logger)

        logger = logging.getLogger('test_logger')

        setup(["start"])
        self.assertTrue(logger.getChild("lbry").isEnabledFor(logging.INFO))
        self.assertFalse(logger.getChild("lbry").isEnabledFor(logging.DEBUG))

        setup(["start", "--verbose"])
        self.assertTrue(logger.getChild("lbry").isEnabledFor(logging.DEBUG))
        self.assertTrue(logger.getChild("lbry").isEnabledFor(logging.INFO))
        self.assertFalse(logger.getChild("torba").isEnabledFor(logging.DEBUG))

        setup(["start", "--verbose", "lbry.extras", "lbry.wallet", "torba.client"])
        self.assertTrue(logger.getChild("lbry.extras").isEnabledFor(logging.DEBUG))
        self.assertTrue(logger.getChild("lbry.wallet").isEnabledFor(logging.DEBUG))
        self.assertTrue(logger.getChild("torba.client").isEnabledFor(logging.DEBUG))
        self.assertFalse(logger.getChild("lbry").isEnabledFor(logging.DEBUG))
        self.assertFalse(logger.getChild("torba").isEnabledFor(logging.DEBUG))


class CLITest(AsyncioTestCase):

    @staticmethod
    def shell(argv):
        actual_output = StringIO()
        with contextlib.redirect_stdout(actual_output):
            with contextlib.redirect_stderr(actual_output):
                try:
                    main(argv)
                except SystemExit as e:
                    print(e.args[0])
        return actual_output.getvalue().strip()

    def test_guess_type(self):
        self.assertEqual('0.3.8', normalize_value('0.3.8'))
        self.assertEqual('0.3', normalize_value('0.3'))
        self.assertEqual(3, normalize_value('3'))
        self.assertEqual(3, normalize_value(3))

        self.assertEqual(
            'VdNmakxFORPSyfCprAD/eDDPk5TY9QYtSA==',
            normalize_value('VdNmakxFORPSyfCprAD/eDDPk5TY9QYtSA==')
        )

        self.assertTrue(normalize_value('TRUE'))
        self.assertTrue(normalize_value('true'))
        self.assertTrue(normalize_value('TrUe'))
        self.assertFalse(normalize_value('FALSE'))
        self.assertFalse(normalize_value('false'))
        self.assertFalse(normalize_value('FaLsE'))
        self.assertTrue(normalize_value(True))

        self.assertEqual('3', normalize_value('3', key="uri"))
        self.assertEqual('0.3', normalize_value('0.3', key="uri"))
        self.assertEqual('True', normalize_value('True', key="uri"))
        self.assertEqual('False', normalize_value('False', key="uri"))

        self.assertEqual('3', normalize_value('3', key="file_name"))
        self.assertEqual('3', normalize_value('3', key="name"))
        self.assertEqual('3', normalize_value('3', key="download_directory"))
        self.assertEqual('3', normalize_value('3', key="channel_name"))
        self.assertEqual('3', normalize_value('3', key="claim_name"))

        self.assertEqual(3, normalize_value('3', key="some_other_thing"))

    def test_help(self):
        self.assertIn('lbrynet [-v] [--api HOST:PORT]', self.shell(['--help']))
        # start is special command, with separate help handling
        self.assertIn('--share-usage-data', self.shell(['start', '--help']))
        # publish is ungrouped command, returns usage only implicitly
        self.assertIn('publish (<name> | --name=<name>)', self.shell(['publish']))
        # publish is ungrouped command, with explicit --help
        self.assertIn('Create or replace a stream claim at a given name', self.shell(['publish', '--help']))
        # account is a group, returns help implicitly
        self.assertIn('Return the balance of an account', self.shell(['account']))
        # account is a group, with explicit --help
        self.assertIn('Return the balance of an account', self.shell(['account', '--help']))
        # account add is a grouped command, returns usage implicitly
        self.assertIn('account_add (<account_name> | --account_name=<account_name>)', self.shell(['account', 'add']))
        # account add is a grouped command, with explicit --help
        self.assertIn('Add a previously created account from a seed,', self.shell(['account', 'add', '--help']))

    def test_help_error_handling(self):
        # person tries `help` command, then they get help even though that's invalid command
        self.assertIn('--config FILE', self.shell(['help']))
        # help for invalid command, with explicit --help
        self.assertIn('--config FILE', self.shell(['nonexistant', '--help']))
        # help for invalid command, implicit
        self.assertIn('--config FILE', self.shell(['nonexistant']))

    def test_version_command(self):
        self.assertEqual(
            "lbrynet {lbrynet_version}".format(**get_platform()), self.shell(['--version'])
        )

    def test_valid_command_daemon_not_started(self):
        self.assertEqual(
            "Could not connect to daemon. Are you sure it's running?",
            self.shell(["publish", 'asd'])
        )

    def test_deprecated_command_daemon_not_started(self):
        actual_output = StringIO()
        with contextlib.redirect_stdout(actual_output):
            main(["channel", "new", "@foo", "1.0"])
        self.assertEqual(
            actual_output.getvalue().strip(),
            "channel_new is deprecated, using channel_create.\n"
            "Could not connect to daemon. Are you sure it's running?"
        )


class DaemonDocsTests(TestCase):

    def test_can_parse_api_method_docs(self):
        failures = []
        for name, fn in Daemon.callable_methods.items():
            try:
                docopt.docopt(fn.__doc__, ())
            except docopt.DocoptLanguageError as err:
                failures.append(f"invalid docstring for {name}, {err.message}")
            except docopt.DocoptExit:
                pass
        if failures:
            self.fail("\n" + "\n".join(failures))
