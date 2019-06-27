/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.component.metadata.ServiceInfo", {
  extend: qx.ui.core.Widget,
  construct: function(metadata) {
    this.base(arguments);

    this.set({
      padding: 5,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    this.__metadata = metadata;

    const main = new qx.ui.container.Composite(new qx.ui.layout.HBox(8));
    main.add(this.__createServiceThumbnail());
    main.add(this.__createMainInfo(), {
      flex: 1
    });
    this._add(main);

    const extraInfo = this.__createExtraInfo();
    const more = new qxapp.desktop.PanelView(this.tr("raw metadata"), extraInfo).set({
      caretSize: 14,
      collapsed: true
    });;
    more.getChildControl("title").setFont("text-12");
    this._add(more, {
      flex: 1
    });
  },

  members: {
    __service: null,
    __metadata: null,

    __createMainInfo: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(8).set({
        alignY: "middle"
      }));

      const title = new qx.ui.basic.Label(this.__metadata.name).set({
        font: "title-16",
        rich: true
      });
      container.add(title);

      const description = new qx.ui.basic.Label(this.__metadata.description).set({
        rich: true
      });
      container.add(description);

      const author = new qx.ui.basic.Label(this.tr("Contact") + ": <b>" + this.__metadata.contact + "</b>").set({
        rich: true
      });
      container.add(author);

      return container;
    },

    __createServiceThumbnail: function() {
      return new qx.ui.basic.Image(this.__metadata.thumbnail || qxapp.utils.Utils.getThumbnailFromString(this.__metadata.key)).set({
        scale: true,
        width: 200,
        height: 120
      });
    },

    __createExtraInfo: function() {
      const container = new qx.ui.container.Scroll();
      container.add(new qxapp.component.widget.JsonTreeWidget(this.__metadata, "serviceDescriptionSettings"));
      return container;
    }
  }
});
