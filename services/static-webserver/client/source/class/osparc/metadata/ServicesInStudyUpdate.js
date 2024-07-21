/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2022 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.metadata.ServicesInStudyUpdate", {
  extend: osparc.metadata.ServicesInStudy,

  /**
    * @param studyData {Object|osparc.data.model.Study} studyData (metadata)
    */
  construct: function(studyData) {
    this.base(arguments, studyData);

    const grid = this._servicesGrid.getLayout();
    grid.setColumnAlign(this.self().GRID_POS.CURRENT_VERSION, "center", "middle");
    grid.setColumnAlign(this.self().GRID_POS.COMPATIBLE_VERSION, "center", "middle");
  },

  statics: {
    GRID_POS: {
      ...osparc.metadata.ServicesInStudy.GRID_POS,
      CURRENT_VERSION: Object.keys(osparc.metadata.ServicesInStudy.GRID_POS).length,
      COMPATIBLE_VERSION: Object.keys(osparc.metadata.ServicesInStudy.GRID_POS).length+1,
      UPDATE_BUTTON: Object.keys(osparc.metadata.ServicesInStudy.GRID_POS).length+2
    },

    anyServiceDeprecated: function(studyData) {
      if ("workbench" in studyData) {
        return osparc.study.Utils.isWorkbenchDeprecated(studyData["workbench"]);
      }
      return false;
    },

    anyServiceRetired: function(studyData) {
      if ("workbench" in studyData) {
        return osparc.study.Utils.isWorkbenchRetired(studyData["workbench"]);
      }
      return false;
    },

    anyServiceInaccessible: function(studyData) {
      if ("workbench" in studyData) {
        const inaccessibles = osparc.study.Utils.getInaccessibleServices(studyData["workbench"]);
        return inaccessibles.length;
      }
      return false;
    },

    getLatestVersion: function(studyData, nodeId) {
      if (nodeId in studyData["workbench"]) {
        const node = studyData["workbench"][nodeId];
        if (osparc.service.Utils.isUpdatable(node)) {
          const latestCompatible = osparc.service.Utils.getLatestCompatible(node["key"], node["version"]);
          if (latestCompatible["version"] !== node["version"]) {
            return latestCompatible["version"];
          }
        }
      }
      return null;
    },

    colorVersionLabel: function(versionLabel, metadata) {
      const isDeprecated = osparc.service.Utils.isDeprecated(metadata);
      const isRetired = osparc.service.Utils.isRetired(metadata);
      if (isDeprecated) {
        versionLabel.set({
          textColor: "text-on-warning", // because the background is always yellow
          backgroundColor: osparc.service.StatusUI.getColor("deprecated"),
          toolTipText: qx.locale.Manager.tr("Service deprecated, please update")
        });
      } else if (isRetired) {
        versionLabel.set({
          textColor: "text-on-warning", // because the background is always red
          backgroundColor: osparc.service.StatusUI.getColor("retired"),
          toolTipText: qx.locale.Manager.tr("Service retired, please update")
        });
      }
    }
  },

  members: {
    __updateAllButton: null,

    _populateIntroText: async function() {
      if (this.self().anyServiceDeprecated(this._studyData)) {
        const deprecatedText = this.tr("Services marked in yellow are deprecated, they will be retired soon. They can be updated by pressing the Update button.");
        const deprecatedLabel = new qx.ui.basic.Label(deprecatedText).set({
          font: "text-14",
          rich: true
        });
        this._introText.add(deprecatedLabel);
      }
      if (this.self().anyServiceRetired(this._studyData)) {
        let retiredText = this.tr("Services marked in red are retired: you cannot use them anymore.<br>If the Update button is disabled, they might require manual intervention to be updated:");
        retiredText += this.tr("<br>- Open the study");
        retiredText += this.tr("<br>- Click on the retired service, download the data");
        retiredText += this.tr("<br>- Upload the data to an updated version");
        const retiredLabel = new qx.ui.basic.Label(retiredText).set({
          font: "text-14",
          rich: true
        });
        this._introText.add(retiredLabel);
      }
      if (this.self().anyServiceInaccessible(this._studyData)) {
        let inaccessibleText = this.tr("Some services' information is not accessible. Please contact service owner:");
        const retiredLabel = new qx.ui.basic.Label(inaccessibleText).set({
          font: "text-14",
          rich: true
        });
        this._introText.add(retiredLabel);
      }
      if (this._introText.getChildren().length === 0) {
        const upToDateLabel = new qx.ui.basic.Label(this.tr("All services are up to date to their latest compatible version.")).set({
          font: "text-14"
        });
        this._introText.add(upToDateLabel);
      }
    },

    __updateService: async function(nodeId, key, version, button) {
      const latestCompatible = osparc.service.Utils.getLatestCompatible(key, version);
      const patchData = {};
      if (key !== latestCompatible["key"]) {
        patchData["key"] = latestCompatible["key"];
      }
      if (version !== latestCompatible["version"]) {
        patchData["version"] = latestCompatible["version"];
      }
      await this._patchNode(nodeId, patchData, button);
    },

    __updateAllServices: async function(updatableNodeIds, button) {
      for (const nodeId of updatableNodeIds) {
        const workbench = this._studyData["workbench"];
        await this.__updateService(nodeId, workbench[nodeId].key, workbench[nodeId].version, button);
      }
    },

    _populateHeader: function() {
      this.base(arguments);

      this._servicesGrid.add(new qx.ui.basic.Label(this.tr("Current")).set({
        font: "title-14"
      }), {
        row: 0,
        column: this.self().GRID_POS.CURRENT_VERSION
      });

      this._servicesGrid.add(new qx.ui.basic.Label(this.tr("Compatible")).set({
        font: "title-14",
        toolTipText: this.tr("Latest compatible version")
      }), {
        row: 0,
        column: this.self().GRID_POS.COMPATIBLE_VERSION
      });

      const updateAllButton = this.__updateAllButton = new osparc.ui.form.FetchButton(this.tr("Update all"), "@MaterialIcons/update/14").set({
        appearance: "form-button",
        padding: [2, 5],
        visibility: "excluded",
        center: true
      });
      this._servicesGrid.add(updateAllButton, {
        row: 0,
        column: this.self().GRID_POS.UPDATE_BUTTON
      });
    },

    _populateRows: function() {
      this.base(arguments);

      const canIWriteStudy = osparc.data.model.Study.canIWrite(this._studyData["accessRights"]);

      const updatableServices = [];
      let i = 0;
      const workbench = this._studyData["workbench"];
      let anyUpdatable = false;
      for (const nodeId in workbench) {
        i++;
        const node = workbench[nodeId];
        const isUpdatable = osparc.service.Utils.isUpdatable(node);
        if (isUpdatable) {
          updatableServices.push(nodeId);
        }
        const currentVersionLabel = new qx.ui.basic.Label(node["version"]).set({
          font: "text-14"
        });
        const nodeMetadata = osparc.service.Store.getMetadata(node["key"], node["version"]);
        this.self().colorVersionLabel(currentVersionLabel, nodeMetadata);
        this._servicesGrid.add(currentVersionLabel, {
          row: i,
          column: this.self().GRID_POS.CURRENT_VERSION
        });

        const compatibleVersionLabel = new qx.ui.basic.Label().set({
          font: "text-14"
        });
        const latestCompatible = osparc.service.Utils.getLatestCompatible(node["key"], node["version"]);
        if (latestCompatible) {
          // updatable
          osparc.service.Store.getService(latestCompatible["key"], latestCompatible["version"])
            .then(metadata => {
              const label = node["key"] === metadata["key"] ? metadata["version"] : metadata["name"] + ":" + metadata["version"];
              compatibleVersionLabel.setValue(label);
            })
            .catch(err => console.error(err));
        } else if (nodeMetadata) {
          // up to date
          compatibleVersionLabel.setValue(nodeMetadata["version"]);
        } else {
          compatibleVersionLabel.setValue(this.tr("Unknown"));
        }
        this._servicesGrid.add(compatibleVersionLabel, {
          row: i,
          column: this.self().GRID_POS.COMPATIBLE_VERSION
        });

        if (latestCompatible && osparc.data.Permissions.getInstance().canDo("study.service.update") && canIWriteStudy) {
          const updateButton = new osparc.ui.form.FetchButton(null, "@MaterialIcons/update/14");
          updateButton.set({
            enabled: isUpdatable
          });
          if ((latestCompatible["key"] === node["key"]) && (latestCompatible["version"] === node["version"])) {
            updateButton.setLabel(this.tr("Up-to-date"));
          }
          if (isUpdatable) {
            updateButton.set({
              appearance: "form-button-outlined",
              padding: [2, 5],
              label: this.tr("Update"),
              center: true
            });
          }
          updateButton.addListener("execute", () => this.__updateService(nodeId, node["key"], node["version"], updateButton), this);
          this._servicesGrid.add(updateButton, {
            row: i,
            column: this.self().GRID_POS.UPDATE_BUTTON
          });

          anyUpdatable |= isUpdatable;
        }
      }

      if (osparc.data.Permissions.getInstance().canDo("study.service.update") && canIWriteStudy && anyUpdatable) {
        const updateAllButton = this.__updateAllButton;
        updateAllButton.show();
        updateAllButton.addListener("execute", () => this.__updateAllServices(updatableServices, updateAllButton), this);
      }
    }
  }
});
