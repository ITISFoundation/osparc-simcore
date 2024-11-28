/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.vipStore.AnatomicalModelDetails", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grow();
    this._setLayout(layout);

    this.__poplulateLayout();
  },

  events: {
    "modelLeased": "qx.event.type.Event",
  },

  properties: {
    anatomicalModelsData: {
      check: "Object",
      init: null,
      nullable: true,
      apply: "__poplulateLayout"
    },
  },

  members: {
    __poplulateLayout: function() {
      this._removeAll();

      const anatomicalModelsData = this.getAnatomicalModelsData();
      if (anatomicalModelsData) {
        const card = this.__createcCard(anatomicalModelsData);
        this._add(card);
      } else {
        const selectModelLabel = new qx.ui.basic.Label().set({
          value: this.tr("Select a model for more details"),
          font: "text-16",
          alignX: "center",
          alignY: "middle",
          allowGrowX: true,
          allowGrowY: true,
        });
        this._add(selectModelLabel);
      }
    },

    __createcCard: function(anatomicalModelsData) {
      console.log(anatomicalModelsData);

      const cardGrid = new qx.ui.layout.Grid(16, 16);
      const cardLayout = new qx.ui.container.Composite(cardGrid);

      const features = anatomicalModelsData["Features"];

      const description = anatomicalModelsData["Description"];
      description.split(" - ").forEach((desc, idx) => {
        const titleLabel = new qx.ui.basic.Label().set({
          value: desc,
          font: "text-16",
          alignX: "center",
          alignY: "middle",
          allowGrowX: true,
          allowGrowY: true,
        });
        cardLayout.add(titleLabel, {
          column: 0,
          row: idx,
          colSpan: 2,
        });
      });

      const thumbnail = new qx.ui.basic.Image().set({
        source: anatomicalModelsData["Thumbnail"],
        alignY: "middle",
        scale: true,
        allowGrowX: true,
        allowGrowY: true,
        allowShrinkX: true,
        allowShrinkY: true,
        maxWidth: 256,
        maxHeight: 256,
      });
      cardLayout.add(thumbnail, {
        column: 0,
        row: 2,
      });

      const moreInfoGrid = new qx.ui.layout.Grid(8, 8);
      const moreInfoLayout = new qx.ui.container.Composite(moreInfoGrid);
      let idx = 0;
      [
        "Name",
        "Version",
        "Sex",
        "Age",
        "Weight",
        "Height",
        "Date",
        "Ethnicity",
      ].forEach(key => {
        if (key.toLowerCase() in features) {
          const titleLabel = new qx.ui.basic.Label().set({
            value: key,
            font: "text-14",
            alignX: "right",
          });
          moreInfoLayout.add(titleLabel, {
            column: 0,
            row: idx,
          });
  
          const nameLabel = new qx.ui.basic.Label().set({
            value: features[key.toLowerCase()],
            font: "text-14",
            alignX: "left",
          });
          moreInfoLayout.add(nameLabel, {
            column: 1,
            row: idx,
          });
  
          idx++;
        }
      });

      if (anatomicalModelsData["DOI"]) {
        const doiTitle = new qx.ui.basic.Label().set({
          value: "DOI",
          font: "text-14",
          alignX: "right",
          marginTop: 16,
        });
        moreInfoLayout.add(doiTitle, {
          column: 0,
          row: idx,
        });
  
        const doiValue = new qx.ui.basic.Label().set({
          value: anatomicalModelsData["DOI"],
          font: "text-14",
          alignX: "left",
          marginTop: 16,
        });
        moreInfoLayout.add(doiValue, {
          column: 1,
          row: idx,
        });
      }

      cardLayout.add(moreInfoLayout, {
        column: 1,
        row: 2,
      });


      const leaseModelButton = new osparc.ui.form.FetchButton().set({
        label: this.tr("Lease model (2 for months)"),
        appearance: "strong-button",
        center: true,
      });
      leaseModelButton.addListener("execute", () => {
        leaseModelButton.setFetching(true);
        setTimeout(() => {
          leaseModelButton.setFetching(false);
          this.fireDataEvent("modelLeased", this.getAnatomicalModelsData()["ID"]);
        }, 2000);
      });
      cardLayout.add(leaseModelButton, {
        column: 0,
        row: 3,
        colSpan: 2,
      });

      return cardLayout;
    },
  }
});
