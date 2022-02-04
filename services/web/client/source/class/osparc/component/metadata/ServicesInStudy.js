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
    grid.setColumnMinWidth(this.self().gridPos.label, 100);
    grid.setColumnMaxWidth(this.self().gridPos.label, 200);
    grid.setColumnFlex(this.self().gridPos.label, 1);
    grid.setColumnAlign(this.self().gridPos.label, "left", "middle");
    grid.setColumnAlign(this.self().gridPos.name, "left", "middle");
    this._setLayout(grid);

    this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    const store = osparc.store.Store.getInstance();
    store.getServicesDAGs()
      .then(services => {
        this.__services = services;
        this._populateLayout();
      });
  },

  statics: {
    gridPos: {
      infoButton: 0,
      label: 1,
      name: 2
    }
  },

  members: {
    __studyData: null,
    __services: null,

    _updateStudy: function(fetchButton) {
      if (fetchButton) {
        fetchButton.setFetching(true);
      }

      this.setEnabled(false);
      const params = {
        url: {
          "studyId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.__studyData = osparc.data.model.Study.deepCloneStudyObject(updatedData);
          this._populateLayout();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong updating the Service"), "ERROR");
          console.error(err);
        })
        .finally(() => {
          if (fetchButton) {
            fetchButton.setFetching(false);
          }
          this.setEnabled(true);
        });
    },

    _populateLayout: function() {
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

      this._populateHeader();
      this._populateRows();
    },

    _populateHeader: function() {
      this._add(new qx.ui.basic.Label(this.tr("Label")).set({
        font: "title-14"
      }), {
        row: 0,
        column: this.self().gridPos.label
      });
      this._add(new qx.ui.basic.Label(this.tr("Name")).set({
        font: "title-14"
      }), {
        row: 0,
        column: this.self().gridPos.name
      });
    },

    _populateRows: function() {
      let i=1;
      const workbench = this.__studyData["workbench"];
      for (const nodeId in workbench) {
        const node = workbench[nodeId];

        const infoButton = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/14");
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

        const nodeMetaData = osparc.utils.Services.getFromObject(this.__services, node["key"], node["version"]);
        const nameLabel = new qx.ui.basic.Label(nodeMetaData["name"]).set({
          font: "text-14",
          toolTipText: node["key"]
        });
        this._add(nameLabel, {
          row: i,
          column: this.self().gridPos.name
        });

        i++;
      }
    }
  }
});
