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


qx.Class.define("osparc.servicecard.Utils", {
  type: "static",

  statics: {
    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createTitle: function(serviceData) {
      const title = new qx.ui.basic.Label().set({
        font: "title-14",
        allowStretchX: true,
        rich: true
      });
      title.setValue(serviceData["name"]);
      return title;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createKey: function(serviceData) {
      const key = new qx.ui.basic.Label().set({
        maxWidth: 220
      });
      key.set({
        value: serviceData["key"],
        toolTipText: serviceData["key"]
      });
      return key;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createVersion: function(serviceData) {
      const key = new qx.ui.basic.Label().set({
        value: serviceData["version"],
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
      const ar = serviceData["access_rights"];
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
      const image = new osparc.component.widget.Thumbnail(null, maxWidth, maxHeight);
      const img = image.getChildControl("image");
      img.set({
        source: "thumbnail" in serviceData && serviceData["thumbnail"] !== "" ? serviceData["thumbnail"] : osparc.dashboard.StudyBrowserButtonItem.SERVICE_ICON
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
            extraInfo.action.callback.call(extraInfo.action.ctx);
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
