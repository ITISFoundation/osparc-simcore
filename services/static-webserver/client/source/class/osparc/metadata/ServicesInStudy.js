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
 *    const servicesInStudy = new osparc.metadata.ServicesInStudy(study);
 *    this.add(servicesInStudy);
 * </pre>
 */

qx.Class.define("osparc.metadata.ServicesInStudy", {
  type: "abstract",
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object|osparc.data.model.Study} studyData (metadata)
    */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._introText = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    this._add(this._introText);

    const grid = this.__grid = new qx.ui.layout.Grid(20, 5);
    grid.setColumnAlign(this.self().GRID_POS.LABEL, "left", "middle");
    grid.setColumnMinWidth(this.self().GRID_POS.LABEL, 80);
    grid.setColumnFlex(this.self().GRID_POS.LABEL, 1);
    this._servicesGrid = new qx.ui.container.Composite(grid);
    this._add(this._servicesGrid);

    this._studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    const servicesInStudy = osparc.study.Utils.extractServices(this._studyData["workbench"]);
    if (servicesInStudy.length) {
      const promises = [];
      servicesInStudy.forEach(srv => promises.push(osparc.store.Services.getService(srv.key, srv.version)));
      Promise.all(promises)
        .then(() => this._populateLayout());
    } else {
      this.__populateEmptyLayout();
    }
  },

  events: {
    "updateService": "qx.event.type.Data"
  },

  statics: {
    GRID_POS: {
      INFO_BUTTON: 0,
      LABEL: 1
    }
  },

  members: {
    _studyData: null,
    _introText: null,
    __grid: null,
    _servicesGrid: null,

    _patchNode: function(nodeId, patchData, fetchButton) {
      if (fetchButton) {
        fetchButton.setFetching(true);
      }
      this.setEnabled(false);

      osparc.info.StudyUtils.patchNodeData(this._studyData, nodeId, patchData)
        .then(() => {
          this.fireDataEvent("updateService", this._studyData);
          this._populateLayout();
        })
        .catch(err => {
          if ("message" in err) {
            osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          } else {
            osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong updating the Service"), "ERROR");
          }
        })
        .finally(() => {
          if (fetchButton) {
            fetchButton.setFetching(false);
          }
          this.setEnabled(true);
        });
    },

    __populateEmptyLayout: function() {
      this._introText.removeAll();

      const emptyStudy = new qx.ui.basic.Label(this.tr("The Study is empty")).set({
        font: "text-14"
      });
      this._introText.add(emptyStudy);
    },

    _populateLayout: function() {
      this._introText.removeAll();
      this._populateIntroText();

      this._servicesGrid.removeAll();
      this._populateHeader();
      this._populateRows();
    },

    _populateIntroText: function() {
      throw new Error("Abstract method called!");
    },

    _populateHeader: function() {
      this._servicesGrid.add(new qx.ui.basic.Label(this.tr("Name")).set({
        font: "title-14"
      }), {
        row: 0,
        column: this.self().GRID_POS.LABEL
      });
      this.__grid.setRowHeight(0, 24);
    },

    _populateRows: function() {
      let i=0;
      const workbench = this._studyData["workbench"];
      for (const nodeId in workbench) {
        i++;
        const node = workbench[nodeId];

        const infoButton = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/14");
        infoButton.addListener("execute", () => {
          const metadata = osparc.store.Services.getMetadata(node["key"], node["version"]);
          if (metadata === null) {
            osparc.FlashMessenger.logAs(this.tr("Service information could not be retrieved"), "WARNING");
            return;
          }
          const serviceDetails = new osparc.info.ServiceLarge(metadata, {
            nodeId,
            studyId: this._studyData["uuid"],
            label: node["label"]
          });
          osparc.info.ServiceLarge.popUpInWindow(serviceDetails);
        }, this);
        this._servicesGrid.add(infoButton, {
          row: i,
          column: this.self().GRID_POS.INFO_BUTTON
        });

        const labelLabel = new qx.ui.basic.Label(node["label"]).set({
          toolTipText: node["label"],
          font: "text-14"
        });
        this._servicesGrid.add(labelLabel, {
          row: i,
          column: this.self().GRID_POS.LABEL
        });
        this.__grid.setRowHeight(i, 24);

        const nodeMetadata = osparc.store.Services.getMetadata(node["key"], node["version"]);
        if (nodeMetadata === null) {
          osparc.FlashMessenger.logAs(this.tr("Some service information could not be retrieved"), "WARNING");
          break;
        }
      }
    }
  }
});
