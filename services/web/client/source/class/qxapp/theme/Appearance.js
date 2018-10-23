/* ************************************************************************

   Copyright: 2018 undefined

   License: MIT license

   Authors: undefined

************************************************************************ */

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
        }
      }
    },
    "pb-listitem": {
      style: function(states) {
        let backgroundColor = "material-button-background";

        if (states.hovered) {
          backgroundColor = "material-button-background-hovered"
        }
        if (states.selected) {
          backgroundColor = "material-button-background-pressed"
        }
        return {
          backgroundColor: backgroundColor
        };
      }
    }
  }
});
