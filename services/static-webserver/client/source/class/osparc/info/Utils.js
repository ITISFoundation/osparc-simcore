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
    },

    extraInfosToGrid: function(extraInfos) {
      const grid = new qx.ui.layout.Grid(8, 5);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      const moreInfo = new qx.ui.container.Composite(grid);

      for (let i=0; i<extraInfos.length; i++) {
        const extraInfo = extraInfos[i];
        moreInfo.add(new qx.ui.basic.Label(extraInfo.label).set({
          font: "text-13"
        }), {
          row: i,
          column: 0
        });

        moreInfo.add(extraInfo.view, {
          row: i,
          column: 1
        });

        if (extraInfo.action) {
          extraInfo.action.button.addListener("execute", () => {
            const cb = extraInfo.action.callback;
            if (typeof cb === "string") {
              extraInfo.action.ctx.fireEvent(cb);
            } else {
              cb.call(extraInfo.action.ctx);
            }
          }, this);
          moreInfo.add(extraInfo.action.button, {
            row: i,
            column: 2
          });
        }
      }

      return moreInfo;
    }
  }
});
