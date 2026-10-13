"""배포 메타데이터 정합성.

버전의 유일한 출처는 **git 태그**입니다 (hatch-vcs). `git tag v0.2.0` 이 곧 0.2.0
릴리스이고, 소스 어디에도 숫자를 적지 않습니다 — 두 곳에 적으면 반드시 어긋납니다.
여기서는 그 구성이 무너지지 않았는지 지킵니다.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

import pykorail

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
#: ``pyproject.toml`` 을 구조로 읽습니다. 문자열 검사는 주석이나 다른 표에 같은 글자가
#: 있어도 통과하므로, 키 하나하나를 봅니다.
PYPROJECT_DATA = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

PROJECT = PYPROJECT_DATA["project"]
TOOL = PYPROJECT_DATA["tool"]


def _classifier_minors() -> list[int]:
    """``project.classifiers`` 에서 파이썬 마이너 버전만 뽑습니다."""
    pattern = re.compile(r"Programming Language :: Python :: 3\.(\d+)")
    return [int(match.group(1)) for classifier in PROJECT["classifiers"] if (match := pattern.fullmatch(classifier))]


class TestVersionSource:
    def test_version_is_dynamic(self) -> None:
        """버전을 pyproject 에 하드코딩하면 태그와 어긋납니다."""
        # when & then
        assert "version" in PROJECT["dynamic"]

    def test_no_hardcoded_version_field(self) -> None:
        # when & then
        assert "version" not in PROJECT

    def test_version_comes_from_vcs(self) -> None:
        # when & then
        assert TOOL["hatch"]["version"]["source"] == "vcs"

    def test_build_requires_hatch_vcs(self) -> None:
        """빌드 백엔드가 태그를 못 읽으면 버전이 0.0.0 으로 나갑니다."""
        # when & then
        assert "hatch-vcs" in PYPROJECT_DATA["build-system"]["requires"]

    def test_fallback_exists_for_gitless_builds(self) -> None:
        """소스 tarball·얕은 체크아웃에서도 빌드가 죽지 않아야 합니다."""
        # when & then
        assert "fallback-version" in TOOL["hatch"]["version"]

    def test_runtime_version_is_resolvable(self) -> None:
        # when & then
        assert pykorail.__version__

    def test_runtime_version_is_pep440(self) -> None:
        """태그가 없는 개발 트리에서는 dev/local 세그먼트가 붙을 수 있습니다."""
        # when & then
        assert re.fullmatch(
            r"\d+\.\d+(\.\d+)?([abc]\d+|rc\d+)?(\.dev\d+)?(\+[\w.]+)?",
            pykorail.__version__,
        ), pykorail.__version__

    def test_source_has_no_version_literal(self) -> None:
        """`__version__ = "0.1.0"` 같은 하드코딩이 되살아나는 것을 막습니다."""
        # given
        init = (Path(__file__).resolve().parent.parent / "src/pykorail/__init__.py").read_text(encoding="utf-8")

        # when
        literal = re.search(r'^__version__ = "', init, re.M)

        # then
        assert literal is None


class TestMetadata:
    def test_name(self) -> None:
        # when & then
        assert PROJECT["name"] == "pykorail"

    def test_requires_python_floor_matches_runtime_guard(self) -> None:
        """``requires-python`` 과 ``_compat.MIN_PYTHON`` 이 같은 하한을 말해야 합니다."""
        # given
        from pykorail._compat import MIN_PYTHON

        # when
        declared = PROJECT["requires-python"]

        # then
        assert declared == ">=" + ".".join(map(str, MIN_PYTHON))

    def test_ruff_target_matches_minimum(self) -> None:
        # given
        from pykorail._compat import MIN_PYTHON

        # when
        target = TOOL["ruff"]["target-version"]

        # then
        assert target == "py{}{}".format(*MIN_PYTHON)

    @pytest.mark.parametrize("minor", [11, 12, 13, 14, 15])
    def test_declares_a_classifier_for_each_supported_minor(self, minor: int) -> None:
        """CI 매트릭스와 classifier 가 어긋나면 사용자가 지원 범위를 오해합니다."""
        # when & then
        assert f"Programming Language :: Python :: 3.{minor}" in PROJECT["classifiers"]

    def test_declares_no_classifier_below_minimum(self) -> None:
        """지원을 끊은 버전의 classifier 가 남아 있으면 PyPI 가 지원 범위를 거짓으로 보여 줍니다."""
        # given
        from pykorail._compat import MIN_PYTHON

        declared = _classifier_minors()

        # when
        dropped = [minor for minor in declared if minor < MIN_PYTHON[1]]

        # then
        assert dropped == []


class TestCoverageGate:
    def test_threshold_is_ninety(self) -> None:
        """커버리지 게이트가 조용히 낮춰지는 것을 막습니다."""
        # given
        addopts = TOOL["pytest"]["ini_options"]["addopts"]

        # when & then
        assert "--cov-fail-under=90" in addopts


class TestWorkflows:
    WORKFLOWS = Path(__file__).resolve().parent.parent / ".github/workflows"

    @pytest.mark.parametrize("name", ["ci.yml", "release.yml"])
    def test_checkout_fetches_tags(self, name: str) -> None:
        """얕은 체크아웃이면 hatch-vcs 가 태그를 못 봐서 0.0.0 이 배포됩니다."""
        # given
        text = (self.WORKFLOWS / name).read_text(encoding="utf-8")

        # when
        checkouts = text.count("actions/checkout@")

        # then
        assert text.count("fetch-depth: 0") == checkouts

    @pytest.mark.parametrize("name", ["ci.yml", "release.yml"])
    def test_matrix_covers_supported_versions(self, name: str) -> None:
        # given
        text = (self.WORKFLOWS / name).read_text(encoding="utf-8")

        # when & then
        assert 'python: ["3.11", "3.12", "3.13", "3.14", "3.15"]' in text
