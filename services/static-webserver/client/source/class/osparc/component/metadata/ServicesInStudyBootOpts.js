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
          if (metadata && osparc.data.model.Node.hasBootModes(metadata)) {
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
          osparc.FlashMessenger.logAs(this.tr("Some service information could not be retrieved"), "WARNING");
          break;
        }
        const canIWrite = osparc.data.model.Study.canIWrite(this._studyData["accessRights"]);
        const hasBootModes = osparc.data.model.Node.hasBootModes(nodeMetaData);
        if (canIWrite && hasBootModes) {
          const bootModeSB = osparc.data.model.Node.getBootModesSelectBox(nodeMetaData, workbench, nodeId);
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
