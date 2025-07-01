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
      const title = osparc.info.Utils.createTitle();
      title.setValue(label);
      return title;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createNodeId: function(instanceUuid) {
      const label = osparc.info.Utils.createLabel();
      label.set({
        value: instanceUuid
      });
      return label;
    },

    /**
      * @param serviceKey {String} Service key
      */
    createKey: function(serviceKey) {
      const key = osparc.info.Utils.createLabel();
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
      const version = osparc.info.Utils.createLabel();
      version.set({
        value: serviceVersion
      });
      return version;
    },

    createVersionDisplay: function(key, version) {
      const versionDisplay = osparc.store.Services.getVersionDisplay(key, version);
      const label = new qx.ui.basic.Label(versionDisplay);
      osparc.utils.Utils.setIdToWidget(label, "serviceVersion");
      return label;
    },

    createReleasedDate: function(key, version) {
      const releasedDate = osparc.store.Services.getReleasedDate(key, version);
      if (releasedDate) {
        const label = new qx.ui.basic.Label();
        label.set({
          value: osparc.utils.Utils.formatDateAndTime(new Date(releasedDate)),
        });
        return label;
      }
      return null;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createContact: function(serviceData) {
      const contact = osparc.store.Support.getMailToLabel(serviceData["contact"], serviceData["name"] + ":" + serviceData["version"]);
      return contact;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    createAuthors: function(serviceData) {
      const authors = new qx.ui.basic.Label().set({
        rich: true,
        wrap: true,
        maxWidth: 220,
      });
      authors.set({
        value: serviceData["authors"].map(author => author["name"]).join(", "),
      });
      serviceData["authors"].forEach(author => {
        const oldTTT = authors.getToolTipText();
        authors.set({
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
        if (ar[myGID]["write"]) {
          permissions = qx.locale.Manager.tr("Write");
        } else if (ar[myGID]["execute"]) {
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
        if (osparc.metadata.Quality.isEnabled(quality)) {
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
      * @param maxHeight {Number} description's maxHeight
      */
    createDescription: function(serviceData) {
      const descriptionLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignY: "middle"
      }));

      const description = new osparc.ui.markdown.Markdown();
      // display markdown link content if that's the case
      if (
        osparc.utils.Utils.isValidHttpUrl(serviceData["description"]) &&
        serviceData["description"].endsWith(".md")
      ) {
        // if it's a link, fetch the content
        fetch(serviceData["description"])
          .then(response => response.blob())
          .then(blob => blob.text())
          .then(markdown => {
            description.setValue(markdown)
          })
          .catch(err => {
            console.error(err);
            description.setValue(serviceData["description"]);
          });
      } else if (serviceData["description"]) {
        description.setValue(serviceData["description"]);
      } else {
        description.setValue(this.tr("No description"));
      }
      descriptionLayout.add(description);

      return descriptionLayout;
    },

    RESOURCES_INFO: {
      "limit": {
        label: qx.locale.Manager.tr("Limit"),
        tooltip: qx.locale.Manager.tr("Runtime check:<br>The service can consume a maximum of 'limit' resources - if it attempts to use more resources than this limit, it will be stopped")
      }
    },

    createResourcesInfo: function() {
      const resourcesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      const label = new qx.ui.basic.Label(qx.locale.Manager.tr("Resources")).set({
        font: "text-13"
      });
      resourcesLayout.add(label);

      const grid = new qx.ui.layout.Grid(10, 5);
      grid.setColumnAlign(0, "right", "middle"); // subservice name
      grid.setColumnAlign(1, "left", "middle"); // resource type
      grid.setColumnAlign(2, "left", "middle"); // resource limit value
      const resourcesInfo = new qx.ui.container.Composite(grid).set({
        allowGrowX: false,
        alignX: "left",
        alignY: "middle"
      });
      resourcesLayout.add(resourcesInfo);

      const limitLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      limitLayout.add(new qx.ui.basic.Label(this.RESOURCES_INFO["limit"].label).set({
        font: "text-13"
      }));
      limitLayout.add(new osparc.ui.hint.InfoHint(this.RESOURCES_INFO["limit"].tooltip));
      resourcesInfo.add(limitLayout, {
        row: 0,
        column: 2
      });

      return resourcesLayout;
    },

    createResourcesInfoCompact: function() {
      const resourcesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      const headerLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const label = new qx.ui.basic.Label(qx.locale.Manager.tr("Resource Limits")).set({
        font: "text-13"
      });
      headerLayout.add(label);
      const infoHint = new osparc.ui.hint.InfoHint(this.RESOURCES_INFO["limit"].tooltip);
      headerLayout.add(infoHint);
      resourcesLayout.add(headerLayout);

      const grid = new qx.ui.layout.Grid(10, 5);
      grid.setColumnAlign(0, "left", "middle"); // resource type
      grid.setColumnAlign(1, "left", "middle"); // resource limit value
      const resourcesInfo = new qx.ui.container.Composite(grid).set({
        allowGrowX: false,
        alignX: "left",
        alignY: "middle"
      });
      resourcesLayout.add(resourcesInfo);

      return resourcesLayout;
    },

    resourcesToResourcesInfo: function(resourcesLayout, imagesResourcesInfo) {
      if (resourcesLayout.getChildren().length < 2) {
        return;
      }
      const layout = resourcesLayout.getChildren()[1];
      let row = 1;
      Object.entries(imagesResourcesInfo).forEach(([imageName, imageInfo]) => {
        layout.add(new qx.ui.basic.Label(imageName).set({
          font: "text-13"
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
              label += " (GiB)";
            }
            layout.add(new qx.ui.basic.Label(label).set({
              font: "text-13"
            }), {
              row,
              column
            });
            column++;
            Object.keys(this.RESOURCES_INFO).forEach(resourceInfoKey => {
              if (resourceInfoKey in resourceInfo) {
                let value = resourceInfo[resourceInfoKey];
                if (resourceKey === "RAM") {
                  value = osparc.utils.Utils.bytesToGiB(value);
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

    resourcesToResourcesInfoCompact: function(resourcesLayout, imagesResourcesInfo) {
      if (resourcesLayout.getChildren().length < 2) {
        return;
      }
      const gridLayout = resourcesLayout.getChildren()[1];

      const compactInfo = {};
      Object.values(imagesResourcesInfo).forEach(imageInfo => {
        const resourcesInfo = imageInfo["resources"];
        Object.keys(resourcesInfo).forEach(resourceKey => {
          if (resourcesInfo[resourceKey]["limit"]) {
            if (!(resourceKey in compactInfo)) {
              compactInfo[resourceKey] = 0;
            }
            compactInfo[resourceKey] += resourcesInfo[resourceKey]["limit"]
          }
        });
      });

      let row = 0;
      Object.entries(compactInfo).forEach(([resourceKey, limitsSumUp]) => {
        let label = resourceKey;
        let value = limitsSumUp;
        if (resourceKey === "RAM") {
          label += " (GiB)";
          value = osparc.utils.Utils.bytesToGiB(value);
        }
        gridLayout.add(new qx.ui.basic.Label(label).set({
          font: "text-13"
        }), {
          row,
          column: 0
        });
        gridLayout.add(new qx.ui.basic.Label(String(value)).set({
          font: "text-13"
        }), {
          row,
          column: 1
        });
        row++;
      });
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    openAccessRights: function(serviceData) {
      const collaboratorsView = new osparc.share.CollaboratorsService(serviceData);
      const title = qx.locale.Manager.tr("Share with Collaborators and Organizations");
      osparc.ui.window.Window.popUpInWindow(collaboratorsView, title, 400, 300);
      return collaboratorsView;
    },

    /**
      * @param serviceData {Object} Serialized Service Object
      */
    openQuality: function(serviceData) {
      const qualityEditor = new osparc.metadata.QualityEditor(serviceData);
      const title = serviceData["name"] + " - " + qx.locale.Manager.tr("Quality Assessment");
      osparc.ui.window.Window.popUpInWindow(qualityEditor, title, 650, 700);
      return qualityEditor;
    }
  }
});
