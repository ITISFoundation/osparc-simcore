/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Theme.define("osparc.theme.Font", {
  extend: osparc.theme.osparc.Font,

  fonts: {
    "text-11-italic": {
      size: 11,
      family: ["Roboto"],
      color: "text",
      italic: true
    }
  }
});
