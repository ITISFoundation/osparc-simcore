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
    "workbench-edge-comp-active": "#777",
    "workbench-edge-api-active": "#BBB",
    "workbench-edge-selected": "#00F",
    "logger-debug-message": "#FFF",
    "logger-info-message": "#FFF",
    "logger-warning-message": "#FF0",
    "logger-error-message": "#F00",
    "background-main-lighter": "#2D2D2D",
    "background-main-lighter+": "#373737",
    "text-placeholder": "text-disabled",
    "text-darker": "text-disabled",
    "tabview-pane-background": "background-main",
    "workbench-start-hint": "#505050",
    "ready-green": "#33925A"
  }
});
