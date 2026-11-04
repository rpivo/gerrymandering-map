from check_pr_size import check, count_changed_lines, is_exempt


def test_lockfiles_are_exempt_anywhere_in_the_tree():
    assert is_exempt("pipeline/uv.lock")
    assert is_exempt("site/pnpm-lock.yaml")
    assert is_exempt("package-lock.json")


def test_generated_site_data_is_exempt():
    assert is_exempt("site/src/data/districts.json")


def test_ordinary_files_are_not_exempt():
    assert not is_exempt("site/src/pages/index.astro")
    assert not is_exempt("pipeline/src/gerry/metrics.py")
    assert not is_exempt("docs/uv.lock.md")


def test_counts_added_plus_removed_and_skips_exempt_and_binary_files():
    numstat = "\n".join(
        [
            "10\t5\tpipeline/src/gerry/metrics.py",
            "3\t0\tREADME.md",
            "4000\t12\tpipeline/uv.lock",
            "900\t900\tsite/src/data/districts.json",
            "-\t-\tsite/public/og.png",
            "",
        ]
    )
    total, exempt = count_changed_lines(numstat)
    assert total == 18
    assert exempt == ["pipeline/uv.lock", "site/src/data/districts.json"]


def test_check_passes_at_the_limit():
    ok, message = check("600\t400\ta.py\n", limit=1000)
    assert ok
    assert "1000" in message


def test_check_fails_over_the_limit_and_says_so():
    ok, message = check("600\t401\ta.py\n", limit=1000)
    assert not ok
    assert "1001" in message
    assert "split" in message.lower()


def test_check_mentions_exempt_files():
    ok, message = check("1\t0\ta.py\n50\t0\tsite/pnpm-lock.yaml\n", limit=1000)
    assert ok
    assert "site/pnpm-lock.yaml" in message
