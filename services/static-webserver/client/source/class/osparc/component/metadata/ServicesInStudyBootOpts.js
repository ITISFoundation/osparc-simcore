/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2022 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.component.metadata.ServicesInStudyBootOpts", {
  extend: osparc.component.metadata.ServicesInStudy,

  /**
    * @param studyData {Object|osparc.data.model.Study} studyData (metadata)
    */
  construct: function(studyData) {
    this.base(arguments, studyData);
  },

  statics: {
    GRID_POS: {
      ...osparc.component.metadata.ServicesInStudy.GRID_POS,
      BOOT_MODE: Object.keys(osparc.component.metadata.ServicesInStudy.GRID_POS).length
    },

    anyBootOptions: function(studyData) {
      if ("workbench" in studyData) {
        for (const nodeId in studyData["workbench"]) {
          const node = studyData["workbench"][nodeId];
          const metadata = osparc.utils.Services.getMetaData(node["key"], node["version"]);
          if (metadata && "boot-options" in metadata) {
            return true;
          }
        }
      }
      return false;
    }
  },

  members: {
    _populateIntroText: function() {
      const text = this.tr("Here you can select in which mode the services will be started:");
      const introText = new qx.ui.basic.Label(text).set({
        font: "text-14"
      });
      this._introText.add(introText);
    },

    __updateBootMode: function(nodeId, newBootModeId) {
      if (!("bootOptions" in this._studyData["workbench"][nodeId])) {
        this._studyData["workbench"][nodeId]["bootOptions"] = {};
      }
      this._studyData["workbench"][nodeId]["bootOptions"] = {
        "boot_mode": newBootModeId
      };

      this._updateStudy();
    },

    _populateHeader: function() {
      this.base(arguments);

      this._servicesGrid.add(new qx.ui.basic.Label(this.tr("Boot Mode")).set({
        font: "title-14",
        toolTipText: this.tr("Select boot type")
      }), {
        row: 0,
        column: this.self().GRID_POS.BOOT_MODE
      });
    },

    _populateRows: function() {
      this.base(arguments);

      let i = 0;
      const workbench = this._studyData["workbench"];
      for (const nodeId in workbench) {
        i++;
        const node = workbench[nodeId];
        const nodeMetaData = osparc.utils.Services.getFromObject(this._services, node["key"], node["version"]);
        if (nodeMetaData === null) {
          osparc.component.message.FlashMessenger.logAs(this.tr("Some service information could not be retrieved"), "WARNING");
          break;
        }
        const canIWrite = osparc.data.model.Study.canIWrite(this._studyData["accessRights"]);
        if (canIWrite && "boot-options" in nodeMetaData && "boot_mode" in nodeMetaData["boot-options"]) {
          const bootModesMD = nodeMetaData["boot-options"]["boot_mode"];
          const bootModeSB = new qx.ui.form.SelectBox();
          const sbItems = [];
          Object.entries(bootModesMD["items"]).forEach(([bootModeId, bootModeMD]) => {
            const sbItem = new qx.ui.form.ListItem(bootModeMD["label"]);
            sbItem.bootModeId = bootModeId;
            bootModeSB.add(sbItem);
            sbItems.push(sbItem);
          });
          let defaultBMId = null;
          if ("bootOptions" in workbench[nodeId] && "boot_mode" in workbench[nodeId]["bootOptions"]) {
            defaultBMId = workbench[nodeId]["bootOptions"]["boot_mode"];
          } else {
            defaultBMId = bootModesMD["default"];
          }
          sbItems.forEach(sbItem => {
            if (defaultBMId === sbItem.bootModeId) {
              bootModeSB.setSelection([sbItem]);
            }
          });
          bootModeSB.addListener("changeSelection", e => {
            const newBootModeId = e.getData()[0].bootModeId;
            this.__updateBootMode(nodeId, newBootModeId);
          }, this);
          this._servicesGrid.add(bootModeSB, {
            row: i,
            column: this.self().GRID_POS.BOOT_MODE
          });
        }
      }
    }
  }
});
