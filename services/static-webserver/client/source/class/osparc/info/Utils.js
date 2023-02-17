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


qx.Class.define("osparc.info.Utils", {
  type: "static",

  statics: {
    createTitle: function() {
      const label = new qx.ui.basic.Label().set({
        font: "text-14",
        maxWidth: 600,
        rich: true,
        wrap: true
      });
      return label;
    },

    createId: function() {
      const label = new qx.ui.basic.Label().set({
        maxWidth: 220
      });
      return label;
    },

    createThumbnail: function(maxWidth, maxHeight = 160) {
      const image = new osparc.ui.basic.Thumbnail(null, maxWidth, maxHeight);
      return image;
    }
  }
});
