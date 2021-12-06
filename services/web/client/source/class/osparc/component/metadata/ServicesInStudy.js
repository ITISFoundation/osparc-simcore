/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Widget that displays the services and their versions included in the Study
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *    const servicesInStudy = new osparc.component.metadata.ServicesInStudy(study);
 *    this.add(servicesInStudy);
 * </pre>
 */

qx.Class.define("osparc.component.metadata.ServicesInStudy", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object|osparc.data.model.Study} studyData (metadata)
    */
  construct: function(studyData) {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(20, 5);
    grid.setColumnFlex(this.self().gridPos.label, 1);
    grid.setColumnAlign(this.self().gridPos.label, "left", "middle");
    grid.setColumnAlign(this.self().gridPos.name, "left", "middle");
    grid.setColumnAlign(this.self().gridPos.currentVersion, "center", "middle");
    grid.setColumnAlign(this.self().gridPos.latestVersion, "center", "middle");
    this._setLayout(grid);

    this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    const store = osparc.store.Store.getInstance();
    store.getServicesDAGs()
      .then(services => {
        this.__services = services;
        this.__populateLayout();
      });
  },

  statics: {
    gridPos: {
      infoButton: 0,
      label: 1,
      name: 2,
      currentVersion: 3,
      latestVersion: 4,
      updateButton: 5,
      bootMode: 6
    }
  },

  members: {
    __studyData: null,
    __services: null,

    __updateService: function(nodeId, newVersion, button) {
      this.setEnabled(false);
      const workbench = this.__studyData["workbench"];
      for (const id in workbench) {
        if (id === nodeId) {
          workbench[nodeId]["version"] = newVersion;
        }
      }

      const params = {
        url: {
          "studyId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      button.setFetching(true);
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.__studyData = osparc.data.model.Study.deepCloneStudyObject(updatedData);
          this.__populateLayout();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong updating the Service"), "ERROR");
          console.error(err);
        })
        .finally(() => {
          button.setFetching(false);
          this.setEnabled(true);
        });
    },

    __updateBootMode: function(nodeId, newBootModeId) {
      if (!("bootOptions" in this.__studyData)) {
        this.__studyData["bootOptions"] = {};
      }
      this.__studyData["bootOptions"][nodeId] = {
        "bootMode": newBootModeId
      };
      console.log("Update Boot Mode", this.__studyData);
      return;

      const params = {
        url: {
          "studyId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.__studyData = osparc.data.model.Study.deepCloneStudyObject(updatedData);
          this.__populateLayout();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong updating the Boot Mode"), "ERROR");
          console.error(err);
        });

    },

    __populateLayout: function() {
      this._removeAll();

      const workbench = this.__studyData["workbench"];
      if (Object.values(workbench).length === 0) {
        this._add(new qx.ui.basic.Label(this.tr("The Study is empty")).set({
          font: "text-14"
        }), {
          row: 0,
          column: this.self().gridPos.label
        });
        return;
      }

      let i=0;

      this._add(new qx.ui.basic.Label(this.tr("Label")).set({
        font: "title-14"
      }), {
        row: i,
        column: this.self().gridPos.label
      });
      this._add(new qx.ui.basic.Label(this.tr("Name")).set({
        font: "title-14"
      }), {
        row: i,
        column: this.self().gridPos.name
      });
      this._add(new qx.ui.basic.Label(this.tr("Current")).set({
        font: "title-14"
      }), {
        row: i,
        column: this.self().gridPos.currentVersion
      });
      this._add(new qx.ui.basic.Label(this.tr("Latest")).set({
        font: "title-14",
        toolTipText: this.tr("Latest compatible patch")
      }), {
        row: i,
        column: this.self().gridPos.latestVersion
      });
      this._add(new qx.ui.basic.Label(this.tr("Boot Mode")).set({
        font: "title-14",
        toolTipText: this.tr("Select boot type")
      }), {
        row: i,
        column: this.self().gridPos.bootMode
      });
      i++;

      for (const nodeId in workbench) {
        const node = workbench[nodeId];

        const nodeMetaData = osparc.utils.Services.getFromObject(this.__services, node["key"], node["version"]);
        const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(this.__services, node["key"], node["version"]);

        const infoButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/info-circle/14");
        infoButton.addListener("execute", () => {
          const metadata = osparc.utils.Services.getMetaData(node["key"], node["version"]);
          const serviceDetails = new osparc.servicecard.Large(metadata);
          const title = this.tr("Service information");
          const width = 600;
          const height = 700;
          osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
        }, this);
        this._add(infoButton, {
          row: i,
          column: this.self().gridPos.infoButton
        });

        const labelLabel = new qx.ui.basic.Label(node["label"]).set({
          font: "text-14"
        });
        this._add(labelLabel, {
          row: i,
          column: this.self().gridPos.label
        });

        const nameLabel = new qx.ui.basic.Label(nodeMetaData["name"]).set({
          font: "text-14",
          toolTipText: node["key"]
        });
        this._add(nameLabel, {
          row: i,
          column: this.self().gridPos.name
        });

        const currentVersionLabel = new qx.ui.basic.Label(node["version"]).set({
          font: "title-14",
          backgroundColor: qx.theme.manager.Color.getInstance().resolve(node["version"] === latestCompatibleMetadata["version"] ? "ready-green" : "warning-yellow")
        });
        this._add(currentVersionLabel, {
          row: i,
          column: this.self().gridPos.currentVersion
        });

        const latestVersionLabel = new qx.ui.basic.Label(latestCompatibleMetadata["version"]).set({
          font: "text-14"
        });
        this._add(latestVersionLabel, {
          row: i,
          column: this.self().gridPos.latestVersion
        });

        const myGroupId = osparc.auth.Data.getInstance().getGroupId();
        const orgIDs = osparc.auth.Data.getInstance().getOrgIds();
        orgIDs.push(myGroupId);
        const canIWrite = osparc.component.permissions.Study.canGroupsWrite(this.__studyData["accessRights"], orgIDs);
        if (osparc.data.Permissions.getInstance().canDo("study.service.update") && canIWrite) {
          const updateButton = new osparc.ui.form.FetchButton(null, "@MaterialIcons/update/14");
          updateButton.set({
            label: node["version"] === latestCompatibleMetadata["version"] ? this.tr("Up-to-date") : this.tr("Update"),
            enabled: node["version"] !== latestCompatibleMetadata["version"]
          });
          updateButton.addListener("execute", () => {
            this.__updateService(nodeId, latestCompatibleMetadata["version"], updateButton);
          }, this);
          this._add(updateButton, {
            row: i,
            column: this.self().gridPos.updateButton
          });

          if ("boot-options" in nodeMetaData && "boot_mode" in nodeMetaData["boot-options"]) {
            const bootModesMD = nodeMetaData["boot-options"]["boot_mode"];
            const bootModeSB = new qx.ui.form.SelectBox();
            Object.entries(bootModesMD).forEach(([bootModeId, bootModeMD]) => {
              const sbItem = new qx.ui.form.ListItem(bootModeMD["label"]);
              sbItem.bootModeId = bootModeId;
              bootModeSB.add(sbItem);
              if (bootModeId === bootModesMD["default"]) {
                bootModeSB.setSelection([sbItem]);
              }
            });
            bootModeSB.addListener("changeSelection", e => {
              let newBootModeId = e.getData()[0].bootModeId;
              this.__updateBootMode(nodeId, newBootModeId);
            }, this);
            this._add(bootModeSB, {
              row: i,
              column: this.self().gridPos.bootMode
            });
          }
        }

        i++;
      }
    }
  }
});
