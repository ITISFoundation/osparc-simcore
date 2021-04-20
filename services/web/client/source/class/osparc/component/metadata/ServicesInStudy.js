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

    const grid = new qx.ui.layout.Grid(20);
    grid.setColumnFlex(this.self().gridPos.name, 1);
    this._setLayout(grid);

    this.__studyData = studyData;

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
      name: 1,
      key: 2,
      currentVersion: 3,
      latestVersion: 4
    }
  },

  members: {
    __services: null,

    __populateLayout: function() {
      let i=0;

      this._add(new qx.ui.basic.Label(this.tr("Name")).set({
        font: "title-14"
      }), {
        row: i,
        column: this.self().gridPos.name
      });
      this._add(new qx.ui.basic.Label(this.tr("Key")).set({
        font: "title-14"
      }), {
        row: i,
        column: this.self().gridPos.key
      });
      this._add(new qx.ui.basic.Label(this.tr("Current")).set({
        font: "title-14"
      }), {
        row: i,
        column: this.self().gridPos.currentVersion
      });
      this._add(new qx.ui.basic.Label(this.tr("Latest")).set({
        font: "title-14"
      }), {
        row: i,
        column: this.self().gridPos.latestVersion
      });
      i++;

      const nodes = Object.values(this.__studyData.workbench);
      nodes.forEach(node => {
        const latestMetadata = osparc.utils.Services.getLatest(this.__services, node["key"]);

        const infoButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/info-circle/14");
        infoButton.addListener("execute", () => {
          const metadata = osparc.utils.Services.getMetaData(node["key"], node["version"]);
          const serviceDetails = new osparc.servicecard.Large(metadata);
          const title = this.tr("Service information");
          const width = 600;
          const height = 700;
          osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
        }, this);

        const nameLabel = new qx.ui.basic.Label(node["label"]).set({
          font: "text-14"
        });

        const parts = node["key"].split("/");
        const keyLabel = new qx.ui.basic.Label(parts[parts.length-1]).set({
          font: "text-14",
          toolTipText: node["key"]
        });

        const currentVersionLabel = new qx.ui.basic.Label(node["version"]).set({
          font: "text-14",
          textAlign: "center"
        });
        if (node["version"] !== latestMetadata["version"]) {
          currentVersionLabel.set({
            backgroundColor: "yellow"
          });
        }

        const latestVersionLabel = new qx.ui.basic.Label(latestMetadata["version"]).set({
          font: "text-14",
          textAlign: "center"
        });

        this._add(infoButton, {
          row: i,
          column: this.self().gridPos.infoButton
        });
        this._add(nameLabel, {
          row: i,
          column: this.self().gridPos.name
        });
        this._add(keyLabel, {
          row: i,
          column: this.self().gridPos.key
        });
        this._add(currentVersionLabel, {
          row: i,
          column: this.self().gridPos.currentVersion
        });
        this._add(latestVersionLabel, {
          row: i,
          column: this.self().gridPos.latestVersion
        });
        i++;
      });
    }
  }
});
