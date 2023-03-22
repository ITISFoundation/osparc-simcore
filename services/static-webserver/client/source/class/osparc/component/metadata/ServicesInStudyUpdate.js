/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2022 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.component.metadata.ServicesInStudyUpdate", {
  extend: osparc.component.metadata.ServicesInStudy,

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
      ...osparc.component.metadata.ServicesInStudy.GRID_POS,
      CURRENT_VERSION: Object.keys(osparc.component.metadata.ServicesInStudy.GRID_POS).length,
      COMPATIBLE_VERSION: Object.keys(osparc.component.metadata.ServicesInStudy.GRID_POS).length+1,
      LATEST_VERSION: Object.keys(osparc.component.metadata.ServicesInStudy.GRID_POS).length+2,
      UPDATE_BUTTON: Object.keys(osparc.component.metadata.ServicesInStudy.GRID_POS).length+3
    },

    updateService: function(studyData, nodeId, newVersion) {
      if (nodeId in studyData["workbench"]) {
        if (newVersion === undefined) {
          const services = osparc.utils.Services.servicesCached;
          const node = studyData["workbench"][nodeId];
          newVersion = osparc.utils.Services.getLatestCompatible(services, node["key"], node["version"]);
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
        const services = osparc.utils.Services.servicesCached;
        const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(services, node["key"], node["version"]);
        if (latestCompatibleMetadata["version"] !== node["version"]) {
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

    _populateIntroText: function() {
      const upToDate = new qx.ui.basic.Label(this.tr("All services are up to date to their latest compatible version")).set({
        font: "text-14"
      });
      this._introText.add(upToDate);
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
      for (const nodeId in workbench) {
        i++;
        const node = workbench[nodeId];
        const nodeMetadata = osparc.utils.Services.getMetaData(node["key"], node["version"]);
        const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(this._services, node["key"], node["version"]);
        const latestMetadata = osparc.utils.Services.getLatest(this._services, node["key"]);
        if (latestCompatibleMetadata === null) {
          osparc.component.message.FlashMessenger.logAs(this.tr("Some service information could not be retrieved"), "WARNING");
          break;
        }
        const autoUpdatable = node["version"] !== latestCompatibleMetadata["version"];
        if (autoUpdatable) {
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

        const compatibleVersionLabel = new qx.ui.basic.Label(latestCompatibleMetadata["version"]).set({
          font: "text-14"
        });
        this.self().colorVersionLabel(compatibleVersionLabel, latestCompatibleMetadata);
        this._servicesGrid.add(compatibleVersionLabel, {
          row: i,
          column: this.self().GRID_POS.COMPATIBLE_VERSION
        });

        const latestVersionLabel = new qx.ui.basic.Label(latestMetadata["version"]).set({
          font: "text-14"
        });
        this._servicesGrid.add(latestVersionLabel, {
          row: i,
          column: this.self().GRID_POS.LATEST_VERSION
        });

        if (osparc.data.Permissions.getInstance().canDo("study.service.update") && canIWriteStudy) {
          const updateButton = new osparc.ui.form.FetchButton(null, "@MaterialIcons/update/14");
          updateButton.set({
            enabled: autoUpdatable
          });
          if (latestCompatibleMetadata["version"] === node["version"]) {
            updateButton.setLabel(this.tr("Up-to-date"));
          }
          if (latestCompatibleMetadata["version"] !== latestMetadata["version"]) {
            updateButton.setLabel(this.tr("Update manually"));
          }
          if (autoUpdatable) {
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
        }
      }

      if (osparc.data.Permissions.getInstance().canDo("study.service.update") && canIWriteStudy) {
        const updateAllButton = this.__updateAllButton;
        updateAllButton.show();
        updateAllButton.addListener("execute", () => this.__updateAllServices(updatableServices, updateAllButton), this);
      }
    }
  }
});
