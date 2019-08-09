/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.component.metadata.ServiceInfo", {
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

    const authors = this.__createAuthors();
    this._add(authors);

    const rawMetadata = this.__createRawMetadata();
    const more = new osparc.desktop.PanelView(this.tr("raw metadata"), rawMetadata).set({
      caretSize: 14
    });
    this._add(more, {
      flex: 1
    });
    more.setCollapsed(true);
    more.getChildControl("title").setFont("text-12");
  },

  members: {
    __service: null,
    __metadata: null,

    __createMainInfo: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(8).set({
        alignY: "middle"
      }));

      const titleContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const title = new qx.ui.basic.Label(this.__metadata.name).set({
        font: "title-16",
        rich: true
      });
      const version = new qx.ui.basic.Label("v" + this.__metadata.version).set({
        rich: true
      });
      titleContainer.add(title);
      titleContainer.add(version);
      container.add(titleContainer);

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
      return new qx.ui.basic.Image(this.__metadata.thumbnail || osparc.utils.Utils.getThumbnailFromString(this.__metadata.key)).set({
        scale: true,
        width: 200,
        height: 120
      });
    },

    __createRawMetadata: function() {
      const container = new qx.ui.container.Scroll();
      container.add(new osparc.component.widget.JsonTreeWidget(this.__metadata, "serviceDescriptionSettings"));
      return container;
    },

    __createAuthors: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      container.add(new qx.ui.basic.Label(this.tr("Authors")).set({
        font: "title-12"
      }));
      for (let i in this.__metadata.authors) {
        const author = this.__metadata.authors[i];
        const authorLine = `${author.name} · ${author.affiliation} · ${author.email}`;
        container.add(new qx.ui.basic.Label(authorLine));
      }
      return container;
    }
  }
});
