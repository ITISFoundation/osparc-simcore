/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2021 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * A toolbar button that serves to fetch or load some data from the server. To indicate that some processing is being done, and
 * that the user has to wait, a rotating special icon is shown meanwhile.
 */
qx.Class.define("osparc.ui.menu.FetchButton", {
  extend: qx.ui.menu.Button,
  include: osparc.ui.mixin.FetchButton
});
