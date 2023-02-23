/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Theme.define("osparc.theme.products.osparc.Appearance", {
  extend: osparc.theme.Appearance,

  appearances: {
    "strong-button": {
      include: "material-button",
      style: state => ({
        decorator: state.hovered ? "strong-bordered-button" : "no-border",
        backgroundColor: "strong-main",
        textColor: "#d2d8dc" // dark theme's text color
      })
    }
  }
});
