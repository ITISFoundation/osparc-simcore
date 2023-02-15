/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.info.ServiceUtils", {
  type: "static",

  statics: {
    /**
      * @param label {String} label
      */
    createTitle: function(label) {
      const title = new qx.ui.basic.Label(label).set({
        font: "title-14",
        allowStretchX: true,
        rich: true
      });
      return title;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createNodeId: function(instaceUuid) {
      const label = new qx.ui.basic.Label().set({
        maxWidth: 220
      });
      label.set({
        value: instaceUuid
      });
      return label;
    },

    /**
      * @param serviceKey {String} Service key
      */
    createKey: function(serviceKey) {
      const key = new qx.ui.basic.Label().set({
        maxWidth: 220
      });
      key.set({
        value: serviceKey,
        toolTipText: serviceKey
      });
      return key;
    },

    /**
      * @param serviceVersion {String} Service version
      */
    createVersion: function(serviceVersion) {
      const key = new qx.ui.basic.Label().set({
        value: serviceVersion,
        maxWidth: 150
      });
      return key;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createContact: function(serviceData) {
      const owner = new qx.ui.basic.Label();
      owner.set({
        value: osparc.utils.Utils.getNameFromEmail(serviceData["contact"]),
        toolTipText: serviceData["contact"]
      });
      return owner;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createAuthors: function(serviceData) {
      const authors = new qx.ui.basic.Label().set({
        rich: true
      });
      serviceData["authors"].forEach(author => {
        const oldVal = authors.getValue();
        const oldTTT = authors.getToolTipText();
        authors.set({
          value: (oldVal ? oldVal : "") + `${author["name"]} <br>`,
          toolTipText: (oldTTT ? oldTTT : "") + `${author["email"]} - ${author["affiliation"]}<br>`
        });
      });
      return authors;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createAccessRights: function(serviceData) {
      let permissions = "";
      const myGID = osparc.auth.Data.getInstance().getGroupId();
      const ar = serviceData["accessRights"];
      if (myGID in ar) {
        if (ar[myGID]["write_access"]) {
          permissions = qx.locale.Manager.tr("Write");
        } else if (ar[myGID]["execute_access"]) {
          permissions = qx.locale.Manager.tr("Execute");
        }
      } else {
        permissions = qx.locale.Manager.tr("Public");
      }
      const accessRights = new qx.ui.basic.Label(permissions);
      return accessRights;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createClassifiers: function(serviceData) {
      const nClassifiers = new qx.ui.basic.Label();
      nClassifiers.setValue(`(${serviceData["classifiers"].length})`);
      return nClassifiers;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createQuality: function(serviceData) {
      const tsrLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2)).set({
        toolTipText: qx.locale.Manager.tr("Ten Simple Rules score")
      });
      const addStars = data => {
        tsrLayout.removeAll();
        const quality = data["quality"];
        if (osparc.component.metadata.Quality.isEnabled(quality)) {
          const tsrRating = new osparc.ui.basic.StarsRating();
          tsrRating.set({
            nStars: 4,
            showScore: true
          });
          osparc.ui.basic.StarsRating.scoreToStarsRating(quality["tsr_current"], quality["tsr_target"], tsrRating);
          tsrLayout.add(tsrRating);
        } else {
          tsrLayout.exclude();
        }
      };
      addStars(serviceData);
      return tsrLayout;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      * @param maxWidth {Number} thumbnail's maxWidth
      * @param maxHeight {Number} thumbnail's maxHeight
      */
    createThumbnail: function(serviceData, maxWidth, maxHeight = 160) {
      const image = new osparc.ui.basic.Thumbnail().set({
        source: "thumbnail" in serviceData && serviceData["thumbnail"] !== "" ? serviceData["thumbnail"] : osparc.dashboard.CardBase.SERVICE_ICON,
        maxWidth,
        maxHeight
      });
      return image;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      * @param maxHeight {Number} description's maxHeight
      */
    createDescription: function(serviceData, maxHeight) {
      const descriptionLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      const label = new qx.ui.basic.Label(qx.locale.Manager.tr("Description")).set({
        font: "title-12"
      });
      descriptionLayout.add(label);

      const description = new osparc.ui.markdown.Markdown().set({
        noMargin: true,
        maxHeight: maxHeight
      });
      description.setValue(serviceData["description"]);
      descriptionLayout.add(description);

      return descriptionLayout;
    },

    createResourcesInfo: function() {
      const resourcesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      const label = new qx.ui.basic.Label(qx.locale.Manager.tr("Resources")).set({
        font: "title-12"
      });
      resourcesLayout.add(label);

      const grid = new qx.ui.layout.Grid(10, 5);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnAlign(2, "left", "middle");
      const resourcesInfo = new qx.ui.container.Composite(grid).set({
        allowGrowX: false,
        alignX: "left",
        alignY: "middle"
      });
      resourcesLayout.add(resourcesInfo);

      const reservationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      reservationLayout.add(new qx.ui.basic.Label(this.RESOURCES_INFO["reservation"].label).set({
        font: "title-12"
      }));
      reservationLayout.add(new osparc.ui.hint.InfoHint(this.RESOURCES_INFO["reservation"].tooltip));
      resourcesInfo.add(reservationLayout, {
        row: 0,
        column: 2
      });
      const limitLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      limitLayout.add(new qx.ui.basic.Label(this.RESOURCES_INFO["limit"].label).set({
        font: "title-12"
      }));
      limitLayout.add(new osparc.ui.hint.InfoHint(this.RESOURCES_INFO["limit"].tooltip));
      resourcesInfo.add(limitLayout, {
        row: 0,
        column: 3
      });

      return resourcesLayout;
    },

    RESOURCES_INFO: {
      "reservation": {
        label: qx.locale.Manager.tr("Reservation"),
        tooltip: qx.locale.Manager.tr("Schedule time check:<br>The service requires this 'reservation' amount of resources to start - if insufficient hardware resources are available, the service will not start")
      },
      "limit": {
        label: qx.locale.Manager.tr("Limit"),
        tooltip: qx.locale.Manager.tr("Runtime check:<br>The service can consume a maximum of 'limit' resources - if it attempts to use more resources than this limit, it will be stopped")
      }
    },

    resourcesToResourcesInfo: function(resourcesLayout, imagesResourcesInfo) {
      const layout = resourcesLayout.getChildren()[1];
      let row = 1;
      Object.entries(imagesResourcesInfo).forEach(([imageName, imageInfo]) => {
        layout.add(new qx.ui.basic.Label(imageName).set({
          font: "title-12"
        }), {
          row,
          column: 0
        });
        if ("resources" in imageInfo) {
          const resourcesInfo = imageInfo["resources"];
          Object.keys(resourcesInfo).forEach(resourceKey => {
            let column = 1;
            const resourceInfo = resourcesInfo[resourceKey];
            let label = resourceKey;
            if (resourceKey === "RAM") {
              label += " (GB)";
            }
            layout.add(new qx.ui.basic.Label(label).set({
              font: "title-12"
            }), {
              row,
              column
            });
            column++;
            Object.keys(this.RESOURCES_INFO).forEach(resourceInfoKey => {
              if (resourceInfoKey in resourceInfo) {
                let value = resourceInfo[resourceInfoKey];
                if (resourceKey === "RAM") {
                  value = osparc.utils.Utils.bytesToGB(value);
                }
                layout.add(new qx.ui.basic.Label(String(value)).set({
                  font: "text-12"
                }), {
                  row,
                  column
                });
                column++;
              }
            });
            row++;
          });
        }
      });
    },

    createExtraInfo: function(extraInfos) {
      const grid = new qx.ui.layout.Grid(5, 3);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      const moreInfo = new qx.ui.container.Composite(grid).set({
        allowGrowX: false,
        alignX: "center",
        alignY: "middle"
      });

      for (let i=0; i<extraInfos.length; i++) {
        const extraInfo = extraInfos[i];
        moreInfo.add(new qx.ui.basic.Label(extraInfo.label).set({
          font: "title-12"
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
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    openAccessRights: function(serviceData) {
      const permissionsView = new osparc.component.permissions.Service(serviceData);
      const title = qx.locale.Manager.tr("Share with Collaborators and Organizations");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
      return permissionsView;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    openQuality: function(serviceData) {
      const qualityEditor = new osparc.component.metadata.QualityEditor(serviceData);
      const title = serviceData["name"] + " - " + qx.locale.Manager.tr("Quality Assessment");
      osparc.ui.window.Window.popUpInWindow(qualityEditor, title, 650, 700);
      return qualityEditor;
    }
  }
});
