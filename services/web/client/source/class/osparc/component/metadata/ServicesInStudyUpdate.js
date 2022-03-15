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

    const grid = this._getLayout();
    grid.setColumnAlign(this.self().gridPosUpd.currentVersion, "center", "middle");
    grid.setColumnAlign(this.self().gridPosUpd.latestVersion, "center", "middle");
  },

  statics: {
    gridPosUpd: {
      currentVersion: 3,
      latestVersion: 4,
      updateButton: 5
    }
  },

  members: {
    __updateAllButton: null,

    __updateService: function(nodeId, newVersion, button) {
      this.setEnabled(false);
      for (const id in this.__studyData["workbench"]) {
        if (id === nodeId) {
          this.__studyData["workbench"][nodeId]["version"] = newVersion;
        }
      }
      this._updateStudy(button);
    },

    __updateAllServices: function(nodeIds, button) {
      this.setEnabled(false);
      for (const nodeId in this.__studyData["workbench"]) {
        if (nodeIds.includes(nodeId)) {
          const node = this.__studyData["workbench"][nodeId];
          const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(this.__services, node["key"], node["version"]);
          this.__studyData["workbench"][nodeId]["version"] = latestCompatibleMetadata["version"];
        }
      }
      this._updateStudy(button);
    },

    _populateHeader: function() {
      this.base(arguments);

      this._add(new qx.ui.basic.Label(this.tr("Current")).set({
        font: "title-14"
      }), {
        row: 0,
        column: this.self().gridPosUpd.currentVersion
      });
      this._add(new qx.ui.basic.Label(this.tr("Latest")).set({
        font: "title-14",
        toolTipText: this.tr("Latest compatible patch")
      }), {
        row: 0,
        column: this.self().gridPosUpd.latestVersion
      });

      const updateAllButton = this.__updateAllButton = new osparc.ui.form.FetchButton(this.tr("Update all"), "@MaterialIcons/update/14");
      this._add(updateAllButton, {
        row: 0,
        column: this.self().gridPosUpd.updateButton
      });
    },

    _populateRows: function() {
      this.base(arguments);

      const updatableServices = [];
      let i = 1;
      const workbench = this.__studyData["workbench"];
      for (const nodeId in workbench) {
        const node = workbench[nodeId];

        const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(this.__services, node["key"], node["version"]);
        const updatable = node["version"] !== latestCompatibleMetadata["version"];
        if (updatable) {
          updatableServices.push(nodeId);
        }

        const currentVersionLabel = new qx.ui.basic.Label(node["version"]).set({
          font: "text-14",
          textColor: updatable ? "text-darker" : "text",
          backgroundColor: updatable ? "warning-yellow" : null
        });
        this._add(currentVersionLabel, {
          row: i,
          column: this.self().gridPosUpd.currentVersion
        });

        const latestVersionLabel = new qx.ui.basic.Label(latestCompatibleMetadata["version"]).set({
          font: "text-14"
        });
        this._add(latestVersionLabel, {
          row: i,
          column: this.self().gridPosUpd.latestVersion
        });

        const myGroupId = osparc.auth.Data.getInstance().getGroupId();
        const orgIDs = osparc.auth.Data.getInstance().getOrgIds();
        orgIDs.push(myGroupId);
        const canIWrite = osparc.component.permissions.Study.canGroupsWrite(this.__studyData["accessRights"], orgIDs);
        if (osparc.data.Permissions.getInstance().canDo("study.service.update") && canIWrite) {
          const updateButton = new osparc.ui.form.FetchButton(null, "@MaterialIcons/update/14");
          updateButton.set({
            label: updatable ? this.tr("Update") : this.tr("Up-to-date"),
            enabled: updatable
          });
          if (updatable) {
            updateButton.setAppearance("strong-button");
          }
          updateButton.addListener("execute", () => this.__updateService(nodeId, latestCompatibleMetadata["version"], updateButton), this);
          this._add(updateButton, {
            row: i,
            column: this.self().gridPosUpd.updateButton
          });
        }

        i++;
      }

      const updateAllButton = this.__updateAllButton;
      updateAllButton.addListener("execute", () => this.__updateAllServices(updatableServices, updateAllButton), this);
      updateAllButton.setEnabled(Boolean(updatableServices.length));
      if (updatableServices.length) {
        updateAllButton.setAppearance("strong-button");
      }
    }
  }
});
