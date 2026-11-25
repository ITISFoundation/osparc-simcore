"""Browser-side helpers reading what the editor shows for a node."""

import logging
import re
from datetime import timedelta
from typing import Any, Final

from playwright.sync_api import (
    Locator,
    Page,
    expect,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential_jitter,
    wait_fixed,
)

from .logging_tools import log_context

_logger = logging.getLogger(__name__)


def wait_for_label_text(page: Page, locator: str, substring: str, timeout: int = 10000) -> Locator:
    page.locator(locator).wait_for(state="visible", timeout=timeout)

    page.wait_for_function(
        f"() => document.querySelector('{locator}').innerText.includes('{substring}')",
        timeout=timeout,
    )

    return page.locator(locator)


def get_node_id_from_service_key(workbench: dict[str, Any], service_key_fragment: str) -> str:
    """Finds the node id in a project's workbench whose service key contains the given fragment."""
    for node_id, node_data in workbench.items():
        if service_key_fragment in node_data["key"]:
            return node_id
    msg = f"Could not find a node with service key containing {service_key_fragment!r} in workbench"
    raise ValueError(msg)


def get_node_id_from_label(workbench: dict[str, Any], label_fragment: str) -> str:
    """Finds the node id in a project's workbench whose label contains the given fragment.

    Preferred over the workbench tree's displayed text since the workbench dict is the
    authoritative source for a node's label.
    """
    matches = [node_id for node_id, node_data in workbench.items() if label_fragment in node_data["label"]]
    available_labels = [node_data["label"] for node_data in workbench.values()]
    if not matches:
        msg = f"Could not find a node with label containing {label_fragment!r} (available: {available_labels})"
        raise ValueError(msg)
    if len(matches) > 1:
        msg = f"Found {len(matches)} nodes with label containing {label_fragment!r} (available: {available_labels})"
        raise ValueError(msg)
    return matches[0]


def get_node_id_from_position(workbench: dict[str, Any], position: int) -> str:
    """Returns the node id at `position` in the workbench (its insertion order).

    Preferred over the workbench tree's DOM order since the workbench dict is the authoritative
    source for a project's nodes and their order.
    """
    node_ids = list(workbench)
    assert 0 <= position < len(node_ids), f"position {position} out of range for workbench with {len(node_ids)} node(s)"
    return node_ids[position]


def _select_node(page: Page, *, node_id: str) -> None:
    """Selects the node with `node_id` in the workbench tree (left panel)."""
    locator = page.locator(f'[osparc-test-id="nodeTreeItem"][osparc-test-key="{node_id}"]')
    assert locator.count() == 1, f"expected exactly one tree item for node {node_id!r}, found {locator.count()}"
    locator.click()


_OUTPUT_FILE_NAMES_MAX_WAITING_TIME: Final[timedelta] = timedelta(seconds=30)

_OUTPUT_FILE_NAMES_WAIT_INTERVAL: Final[timedelta] = timedelta(seconds=5)


def _read_output_file_names(
    page: Page,
    *,
    node_id: str,
    path_filter: str,
    expected_file_names: list[str],
    open_outputs_folder: bool,
) -> list[str]:
    # the frontend may still be rendering the file list right after the outputs API responds, so
    # this is retried until it matches (or times out). NOTE: the mismatch case is expected/routine
    # here, so it's kept out of `log_context` to avoid logging a full traceback on every retry.
    page.get_by_test_id("folderGridView").click()
    items = page.get_by_test_id("FolderViewerItem")

    if open_outputs_folder:
        outputs_found = False
        for index in range(items.count()):
            item = items.nth(index)
            if "output" in (item.text_content() or ""):
                item.dblclick()
                outputs_found = True
        assert outputs_found, f"outputs folder not found for node {node_id} ({path_filter})"
        items = page.get_by_test_id("FolderViewerItem")

    actual_file_names = sorted([(name or "").removesuffix("\ue24d") for name in items.all_text_contents()])
    missing_file_names = sorted(set(expected_file_names) - set(actual_file_names))
    unexpected_file_names = sorted(set(actual_file_names) - set(expected_file_names))
    if missing_file_names or unexpected_file_names:
        msg = f"Node {node_id} outputs not ready yet: missing={missing_file_names} unexpected={unexpected_file_names}"
        raise AssertionError(msg)

    _logger.info("✅ Node %s outputs match expected file names: %s", node_id, actual_file_names)
    return actual_file_names


@retry(
    stop=stop_after_delay(_OUTPUT_FILE_NAMES_MAX_WAITING_TIME),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
    wait=wait_exponential_jitter(max=_OUTPUT_FILE_NAMES_WAIT_INTERVAL.total_seconds()),
    before_sleep=before_sleep_log(_logger, logging.INFO),
)
def _check_node_files_panel(
    page: Page,
    *,
    study_id: str,
    node_id: str,
    expected_file_names: list[str],
    open_outputs_folder: bool,
    app_mode: bool,
) -> None:
    with log_context(logging.INFO, "Opening node files panel"):
        path_filter = f"{study_id}/{node_id}"
        with page.expect_response(
            re.compile(r"storage/locations/0/paths\?file_filter="),
            timeout=_OUTPUT_FILE_NAMES_MAX_WAITING_TIME.total_seconds() * 1000,
        ):
            if app_mode:
                page.get_by_test_id("outputsBtn").click()
            page.get_by_test_id("nodeFilesBtn").click()

    try:
        _read_output_file_names(
            page,
            node_id=node_id,
            path_filter=path_filter,
            expected_file_names=expected_file_names,
            open_outputs_folder=open_outputs_folder,
        )
    finally:
        with log_context(logging.INFO, "Closing node files panel"):
            page.get_by_test_id("nodeDataManagerCloseBtn").click()


def check_node_files_panel(
    page: Page,
    *,
    study_id: str,
    workbench: dict[str, Any],
    node_position: int | None = None,
    node_name: str | None = None,
    node_id: str | None = None,
    expected_file_names: list[str],
    open_outputs_folder: bool = False,
    app_mode: bool = False,
) -> None:
    """Opens a node's output files panel and asserts it contains exactly `expected_file_names`.

    The node is identified by exactly one of `node_id`, `node_position` (its index in
    `workbench`) or `node_name` (its label in `workbench`). `workbench` is the project's
    authoritative source of node ids/labels/order, so the lookup never depends on the fragile
    workbench tree's DOM order/displayed text.

    Port of the legacy `TutorialBase.checkNodeOutputs()` /
    `TutorialBase.checkNodeOutputsAppMode()`.
    """
    if node_id is None:
        assert (node_position is None) != (node_name is None), (
            "either node_id, node_position or node_name must be provided"
        )
        if node_position is not None:
            node_id = get_node_id_from_position(workbench, node_position)
        else:
            assert node_name is not None
            node_id = get_node_id_from_label(workbench, node_name)
    assert node_id in workbench, f"node {node_id!r} not found in workbench"
    _select_node(page, node_id=node_id)

    with log_context(logging.INFO, f"Checking node {node_id=} files panel"):
        _check_node_files_panel(
            page,
            study_id=study_id,
            node_id=node_id,
            expected_file_names=expected_file_names,
            open_outputs_folder=open_outputs_folder,
            app_mode=app_mode,
        )


_NODE_OUTPUT_LINK_MAX_WAITING_TIME: Final[timedelta] = timedelta(minutes=10)

_NODE_OUTPUT_LINK_CLEARED_MAX_WAITING_TIME: Final[timedelta] = timedelta(minutes=5)

_NODE_OUTPUT_LINK_CLEARED_STABLE_TIME: Final[timedelta] = timedelta(seconds=30)

_NODE_OUTPUT_LINK_POLL_INTERVAL: Final[timedelta] = timedelta(seconds=2)


def _visible_output_link(page: Page, *, port_key: str) -> Locator:
    """Visible value widget of the node output ``port_key`` in the Outputs panel.

    Only visible matches are considered: removed qooxdoo widgets can leave hidden
    nodes with the same test id in the DOM.
    """
    return page.get_by_test_id(f"nodeOutputValue_{port_key}").filter(visible=True).first


def wait_for_node_output_link(page: Page, *, port_key: str, filename: str) -> None:
    """Waits until the output ``port_key`` shows a link to the file ``filename``.

    The node must already be selected so that its Outputs panel is shown.
    """
    expect(_visible_output_link(page, port_key=port_key)).to_contain_text(
        filename, timeout=_NODE_OUTPUT_LINK_MAX_WAITING_TIME.total_seconds() * 1000
    )


@retry(
    stop=stop_after_delay(_NODE_OUTPUT_LINK_CLEARED_MAX_WAITING_TIME),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
    wait=wait_fixed(_NODE_OUTPUT_LINK_POLL_INTERVAL.total_seconds()),
    before_sleep=before_sleep_log(_logger, logging.INFO),
)
def wait_for_node_output_link_cleared(page: Page, *, port_key: str, filename: str) -> None:
    """Waits until the output ``port_key`` no longer links to ``filename`` and stays that way.

    The widget must first stop linking to ``filename``, then keep doing so for
    ``_NODE_OUTPUT_LINK_CLEARED_STABLE_TIME``. A single pass is not enough: the row is
    re-rendered on updates, so the check could transiently succeed while an old widget is
    detached even if the file is then listed again. A regression raises and is retried.
    """

    def _read_link_text() -> str | None:
        value = _visible_output_link(page, port_key=port_key)
        return value.text_content() if value.count() > 0 else None

    text = _read_link_text()
    assert text is not None, f"no visible output link widget for port {port_key!r}"
    assert filename not in text, f"output {port_key!r} still links to {filename!r} (text: {text!r})"

    page.wait_for_timeout(_NODE_OUTPUT_LINK_CLEARED_STABLE_TIME.total_seconds() * 1000)
    text = _read_link_text()
    assert text is not None, f"no visible output link widget for port {port_key!r}"
    assert filename not in text, f"output {port_key!r} links to {filename!r} again (text: {text!r})"
