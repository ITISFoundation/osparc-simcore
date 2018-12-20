/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Theme.define("qxapp.theme.Color", {
  extend: osparc.theme.osparcdark.Color,

  colors: {
    "workbench-link-comp-active": "#777",
    "workbench-link-api-active": "#BBB",
    "workbench-link-selected": "#00F",
    "logger-debug-message": "#FFF",
    "logger-info-message": "#FFF",
    "logger-warning-message": "#FF0",
    "logger-error-message": "#F00"
  }
});
