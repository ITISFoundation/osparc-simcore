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
    grid.setColumnAlign(this.self().GRID_POS.LATEST_VERSION, "center", "middle");
  },

  statics: {
    GRID_POS: {
      ...osparc.metadata.ServicesInStudy.GRID_POS,
      CURRENT_VERSION: Object.keys(osparc.metadata.ServicesInStudy.GRID_POS).length,
      COMPATIBLE_VERSION: Object.keys(osparc.metadata.ServicesInStudy.GRID_POS).length+1,
      LATEST_VERSION: Object.keys(osparc.metadata.ServicesInStudy.GRID_POS).length+2,
      UPDATE_BUTTON: Object.keys(osparc.metadata.ServicesInStudy.GRID_POS).length+3
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

    anyServiceInaccessible: async function(studyData) {
      if ("workbench" in studyData) {
        const store = osparc.store.Store.getInstance();
        const inaccesibles = await store.getInaccessibleServices(studyData);
        return inaccesibles.length;
      }
      return false;
    },

    updateService: function(studyData, nodeId, newVersion) {
      if (nodeId in studyData["workbench"]) {
        if (newVersion === undefined) {
          const node = studyData["workbench"][nodeId];
          newVersion = osparc.utils.Services.getLatestCompatible(null, node["key"], node["version"]);
        }
        for (const id in studyData["workbench"]) {
          if (id === nodeId) {
            studyData["workbench"][nodeId]["version"] = newVersion;
          }
        }
      }
    },

    updateAllServices: function(studyData, updatableNodeIds) {
      for (const nodeId in studyData["workbench"]) {
        if (updatableNodeIds && !updatableNodeIds.includes(nodeId)) {
          continue;
        }
        const node = studyData["workbench"][nodeId];
        if (osparc.utils.Services.isUpdatable(node)) {
          const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(null, node["key"], node["version"]);
          this.self().updateService(studyData, nodeId, latestCompatibleMetadata["version"]);
        }
      }
    },

    colorVersionLabel: function(versionLabel, metadata) {
      const isDeprecated = osparc.utils.Services.isDeprecated(metadata);
      const isRetired = osparc.utils.Services.isRetired(metadata);
      if (isDeprecated) {
        versionLabel.set({
          textColor: "contrasted-text-dark",
          backgroundColor: osparc.utils.StatusUI.getColor("deprecated"),
          toolTipText: qx.locale.Manager.tr("Service deprecated, please update")
        });
      } else if (isRetired) {
        versionLabel.set({
          textColor: "contrasted-text-dark",
          backgroundColor: osparc.utils.StatusUI.getColor("retired"),
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
      if (await this.self().anyServiceInaccessible(this._studyData)) {
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

    __updateService: function(nodeId, newVersion, button) {
      this.setEnabled(false);
      this.self().updateService(this._studyData, nodeId, newVersion);
      this._updateStudy(button);
    },

    __updateAllServices: function(updatableNodeIds, button) {
      this.setEnabled(false);
      this.self().updateAllServices(this._studyData, updatableNodeIds);
      this._updateStudy(button);
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

      this._servicesGrid.add(new qx.ui.basic.Label(this.tr("Latest")).set({
        font: "title-14",
        toolTipText: this.tr("Latest available version")
      }), {
        row: 0,
        column: this.self().GRID_POS.LATEST_VERSION
      });

      const updateAllButton = this.__updateAllButton = new osparc.ui.form.FetchButton(this.tr("Update all"), "@MaterialIcons/update/14").set({
        backgroundColor: "strong-main",
        visibility: "excluded"
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
        const nodeMetadata = osparc.utils.Services.getMetaData(node["key"], node["version"]);
        const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(this._services, node["key"], node["version"]);
        if (latestCompatibleMetadata === null) {
          osparc.FlashMessenger.logAs(this.tr("Some service information could not be retrieved"), "WARNING");
        }
        const isUpdatable = osparc.utils.Services.isUpdatable(node);
        if (isUpdatable) {
          updatableServices.push(nodeId);
        }
        const currentVersionLabel = new qx.ui.basic.Label(node["version"]).set({
          font: "text-14"
        });
        this.self().colorVersionLabel(currentVersionLabel, nodeMetadata);
        this._servicesGrid.add(currentVersionLabel, {
          row: i,
          column: this.self().GRID_POS.CURRENT_VERSION
        });

        if (latestCompatibleMetadata) {
          const compatibleVersionLabel = new qx.ui.basic.Label(latestCompatibleMetadata["version"]).set({
            font: "text-14"
          });
          this.self().colorVersionLabel(compatibleVersionLabel, latestCompatibleMetadata);
          this._servicesGrid.add(compatibleVersionLabel, {
            row: i,
            column: this.self().GRID_POS.COMPATIBLE_VERSION
          });
        } else if (nodeMetadata === null) {
          const compatibleVersionLabel = new qx.ui.basic.Label(this.tr("Unknown")).set({
            font: "text-14"
          });
          this._servicesGrid.add(compatibleVersionLabel, {
            row: i,
            column: this.self().GRID_POS.COMPATIBLE_VERSION
          });
        }

        const latestMetadata = osparc.utils.Services.getLatest(this._services, node["key"]);
        const latestVersionLabel = new qx.ui.basic.Label(latestMetadata["version"]).set({
          font: "text-14"
        });
        this._servicesGrid.add(latestVersionLabel, {
          row: i,
          column: this.self().GRID_POS.LATEST_VERSION
        });

        if (latestCompatibleMetadata && osparc.data.Permissions.getInstance().canDo("study.service.update") && canIWriteStudy) {
          const updateButton = new osparc.ui.form.FetchButton(null, "@MaterialIcons/update/14");
          updateButton.set({
            enabled: isUpdatable
          });
          if (latestCompatibleMetadata["version"] === node["version"]) {
            updateButton.setLabel(this.tr("Up-to-date"));
          }
          if (latestCompatibleMetadata["version"] !== latestMetadata["version"]) {
            updateButton.setLabel(this.tr("Update manually"));
          }
          if (isUpdatable) {
            updateButton.set({
              backgroundColor: "strong-main",
              label: this.tr("Update")
            });
          }
          updateButton.addListener("execute", () => this.__updateService(nodeId, latestCompatibleMetadata["version"], updateButton), this);
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
