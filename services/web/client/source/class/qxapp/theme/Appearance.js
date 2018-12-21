/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint no-warning-comments: "off" */

qx.Theme.define("qxapp.theme.Appearance", {
  extend: osparc.theme.osparcdark.Appearance,

  appearances: {
    "pb-list": {
      include: "list",
      alias:   "list",
      style: function(states) {
        return {
          decorator: null,
          padding: [0, 0]
        };
      }
    },
    "pb-listitem":  {
      // FIXME
      include: "material-button",
      // alias:   "material-button",
      style: function(states) {
        let style = {
          decorator: null,
          padding: [0, 0],
          backgroundColor: "transparent"
        };
        if (states.hovered) {
          style.backgroundColor = "#444";
        }
        if (states.selected) {
          style.backgroundColor = "#555";
        }
        return style;
      }
    }
  }
});
