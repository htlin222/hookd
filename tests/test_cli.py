from hookd.cli import build_parser


def test_parser_setup():
    parser = build_parser()
    args = parser.parse_args(["setup"])
    assert args.command == "setup"


def test_parser_status():
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_parser_logs():
    parser = build_parser()
    args = parser.parse_args(["logs"])
    assert args.command == "logs"


def test_parser_test_event():
    parser = build_parser()
    args = parser.parse_args(["test", "--event", "push"])
    assert args.event == "push"


def test_parser_test_default_event():
    parser = build_parser()
    args = parser.parse_args(["test"])
    assert args.event == "push"


def test_parser_edit():
    parser = build_parser()
    args = parser.parse_args(["edit"])
    assert args.command == "edit"


def test_parser_rotate():
    parser = build_parser()
    args = parser.parse_args(["rotate"])
    assert args.command == "rotate"


def test_parser_disable():
    parser = build_parser()
    args = parser.parse_args(["disable"])
    assert args.command == "disable"


def test_parser_enable():
    parser = build_parser()
    args = parser.parse_args(["enable"])
    assert args.command == "enable"


def test_parser_no_command():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.command is None
