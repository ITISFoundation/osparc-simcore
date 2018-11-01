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
        };
      }
    },
    "pb-listitem": "material-button"
  }
});
