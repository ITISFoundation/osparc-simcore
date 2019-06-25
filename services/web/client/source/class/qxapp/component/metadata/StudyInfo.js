/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.metadata.StudyInfo", {
  extend: qx.ui.core.Widget,
  construct: function(study) {
    this.base(arguments);

    this.set({
      padding: 5,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    this.__study = study;

    const main = new qx.ui.container.Composite(new qx.ui.layout.HBox(8));
    main.add(this.__createStudyThumbnail());
    main.add(this.__createMainInfo(), {
      flex: 1
    });
    this._add(main);
    
    const extraInfo = this.__createExtraInfo();
    const more = new qxapp.desktop.PanelView(this.tr("more information"), extraInfo).set({
      caretSize: 14,
      collapsed: true
    });;
    more.getChildControl("title").setFont("text-12");
    this._add(more);
  },

  members: {
    __study: null,

    __createMainInfo: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));

      const title = new qx.ui.basic.Label(this.__study.getName()).set({
        font: "title-16",
        rich: true
      });
      container.add(title);
  
      const description = new qx.ui.basic.Label(this.__study.getDescription()).set({
        rich: true
      });
      container.add(description);
  
      const author = new qx.ui.basic.Label(this.tr("Owner") + ": <b>" + this.__study.getPrjOwner() + "</b>").set({
        rich: true
      });
      container.add(author);

      return container;
    },

    __createStudyThumbnail: function() {
      return new qx.ui.basic.Image(qxapp.utils.Utils.getThumbnailFromUuid(this.__study.getUuid())).set({
        scale: true,
        width: 200,
        height: 120
      });
    },

    __createExtraInfo: function() {
      const layout = new qx.ui.layout.Grid(8);
      layout.setColumnAlign(0, "right", "middle");
      layout.setColumnAlign(1, "left", "middle");

      const container = new qx.ui.container.Composite(layout);

      const dateFormatter = (date) => {
        return date.toLocaleString();
      };

      container.add(new qx.ui.basic.Label(this.tr("Creation date")), {
        column: 0,
        row: 0
      });
      const creation = new qx.ui.basic.Label(dateFormatter(this.__study.getCreationDate()));
      container.add(creation, {
        column: 1,
        row: 0
      });

      container.add(new qx.ui.basic.Label(this.tr("Last modified")), {
        column: 0,
        row: 1
      });
      const last = new qx.ui.basic.Label(dateFormatter(this.__study.getCreationDate()));
      container.add(last, {
        column: 1,
        row: 1
      });

      return container;
    }
  }
});