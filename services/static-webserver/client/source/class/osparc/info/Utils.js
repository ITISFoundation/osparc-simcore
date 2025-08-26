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

    createLabel: function() {
      const label = new qx.ui.basic.Label().set({
        maxWidth: 220
      });
      return label;
    },

    createThumbnail: function(maxWidth, maxHeight = 160) {
      const image = new osparc.ui.basic.Thumbnail(null, maxWidth, maxHeight);
      return image;
    },

    infoElementsToLayout: function(infoElements, isStudy = true) {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const decorateAction = action => {
          action.button.set({
            alignY: "middle",
          });
          action.button.addListener("execute", () => {
            const cb = action.callback;
            if (typeof cb === "string") {
              action.ctx.fireEvent(cb);
            } else {
              cb.call(action.ctx);
            }
          }, this);
      };

      if ("TITLE" in infoElements) {
        const extraInfo = infoElements["TITLE"];
        const titleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

        if (extraInfo.action && extraInfo.action.button) {
          decorateAction(extraInfo.action);
          titleLayout.add(extraInfo.action.button);
        }

        if (extraInfo.view) {
          titleLayout.add(extraInfo.view, {
            flex: 1,
          });
        }

        container.add(titleLayout);
      }


      const centerLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      if ("THUMBNAIL" in infoElements) {
        const extraInfo = infoElements["THUMBNAIL"];
        const thumbnailLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(8));

        if (extraInfo.action && extraInfo.action.button) {
          decorateAction(extraInfo.action);
          thumbnailLayout.add(extraInfo.action.button);
        }

        if (extraInfo.view) {
          thumbnailLayout.add(extraInfo.view, {
            flex: 1,
          });
        }

        centerLayout.add(thumbnailLayout);
      }

      const gridKeys = isStudy ? [
        "AUTHOR",
        "ACCESS_RIGHTS",
        "CREATED",
        "MODIFIED",
        "TAGS",
        "LOCATION",
      ] : [
        "SERVICE_ID",
        "KEY",
        "INTEGRATION_VERSION",
        "VERSION",
        "DATE",
        "CONTACT",
        "AUTHORS",
        "ACCESS_RIGHTS",
        "DESCRIPTION_ONLY",
      ];

      const grid = new qx.ui.layout.Grid(6, 6);
      grid.setColumnAlign(0, "right", "middle"); // titles
      const gridLayout = new qx.ui.container.Composite(grid);

      let row = 0;
      gridKeys.forEach(key => {
        if (key in infoElements) {
          const infoElement = infoElements[key];

          let col = 0;
          if (infoElement.label) {
            const title = new qx.ui.basic.Label(infoElement.label).set({
              alignX: "right",
            });
            gridLayout.add(title, {
              row,
              column: col + 0,
            });
          }
          col++;

          if (infoElement.action && infoElement.action.button) {
            decorateAction(infoElement.action);
            gridLayout.add(infoElement.action.button, {
              row,
              column: col + 1,
            });
          }
          col++;

          if (infoElement.view) {
            gridLayout.add(infoElement.view, {
              row,
              column: col + 2,
            });
          }
          col++;
          row++;
        }
      });
      centerLayout.add(gridLayout, {
        flex: 1,
      });
      container.add(centerLayout);

      if ("DESCRIPTION" in infoElements) {
        const infoElement = infoElements["DESCRIPTION"];
        const descriptionLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

        if (infoElement.action && infoElement.action.button) {
          decorateAction(infoElement.action);
          descriptionLayout.add(infoElement.action.button);
        }

        if (infoElement.view) {
          descriptionLayout.add(infoElement.view, {
            flex: 1,
          });
        }

        container.add(descriptionLayout);
      }

      return container;
    },

    extraInfosToGrid: function(extraInfos) {
      const grid = new qx.ui.layout.Grid(8, 5);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      const moreInfo = new qx.ui.container.Composite(grid);

      for (let i=0; i<extraInfos.length; i++) {
        const extraInfo = extraInfos[i];
        if (!extraInfo.view) {
          continue;
        }

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

        if (extraInfo.action && extraInfo.action.button) {
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
