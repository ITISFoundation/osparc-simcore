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
    grid.setColumnMinWidth(this.self().GRID_POS.LABEL, 80);
    grid.setColumnMaxWidth(this.self().GRID_POS.LABEL, 180);
    grid.setColumnFlex(this.self().GRID_POS.LABEL, 1);
    grid.setColumnAlign(this.self().GRID_POS.LABEL, "left", "middle");
    grid.setColumnAlign(this.self().GRID_POS.NAME, "left", "middle");
    grid.setColumnMinWidth(this.self().GRID_POS.NAME, 80);
    grid.setColumnMaxWidth(this.self().GRID_POS.NAME, 180);
    this._setLayout(grid);

    this._studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    const servicesInStudy = osparc.utils.Study.extractServices(this._studyData["workbench"]);
    if (servicesInStudy.length) {
      const store = osparc.store.Store.getInstance();
      store.getServicesOnly()
        .then(services => {
          this._services = services;
          this._populateLayout();
        });
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
      LABEL: 1,
      NAME: 2
    }
  },

  members: {
    _studyData: null,
    _services: null,

    _updateStudy: function(fetchButton) {
      if (fetchButton) {
        fetchButton.setFetching(true);
      }

      this.setEnabled(false);
      const params = {
        url: {
          "studyId": this._studyData["uuid"]
        },
        data: this._studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this._studyData = osparc.data.model.Study.deepCloneStudyObject(updatedData);
          this.fireDataEvent("updateService", updatedData);
          this._populateLayout();
        })
        .catch(err => {
          if ("message" in err) {
            osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          } else {
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong updating the Service"), "ERROR");
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
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("The Study is empty")).set({
        font: "text-14"
      }), {
        row: 0,
        column: this.self().GRID_POS.LABEL
      });
    },

    _populateLayout: function() {
      this._removeAll();

      this._populateHeader();
      this._populateRows();
    },

    _populateHeader: function() {
      this._add(new qx.ui.basic.Label(this.tr("Label")).set({
        font: "title-14"
      }), {
        row: 0,
        column: this.self().GRID_POS.LABEL
      });
      this._add(new qx.ui.basic.Label(this.tr("Name")).set({
        font: "title-14"
      }), {
        row: 0,
        column: this.self().GRID_POS.NAME
      });
    },

    _populateRows: function() {
      let i=0;
      const workbench = this._studyData["workbench"];
      for (const nodeId in workbench) {
        i++;
        const node = workbench[nodeId];

        const infoButton = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/14");
        infoButton.addListener("execute", () => {
          const metadata = osparc.utils.Services.getMetaData(node["key"], node["version"]);
          const serviceDetails = new osparc.servicecard.Large(metadata, {
            nodeId,
            label: node["label"]
          });
          const title = this.tr("Service information");
          const width = 600;
          const height = 700;
          osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
        }, this);
        this._add(infoButton, {
          row: i,
          column: this.self().GRID_POS.INFO_BUTTON
        });

        const labelLabel = new qx.ui.basic.Label(node["label"]).set({
          toolTipText: node["label"],
          font: "text-14"
        });
        this._add(labelLabel, {
          row: i,
          column: this.self().GRID_POS.LABEL
        });

        const nodeMetaData = osparc.utils.Services.getFromObject(this._services, node["key"], node["version"]);
        if (nodeMetaData === null) {
          osparc.component.message.FlashMessenger.logAs(this.tr("Some service information could not be retrieved"), "WARNING");
          break;
        }
        const nameLabel = new qx.ui.basic.Label(nodeMetaData["name"]).set({
          toolTipText: node["key"],
          font: "text-14"
        });
        this._add(nameLabel, {
          row: i,
          column: this.self().GRID_POS.NAME
        });
      }
    }
  }
});
