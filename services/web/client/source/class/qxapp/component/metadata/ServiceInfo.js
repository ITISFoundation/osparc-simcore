/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
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

    this.__createServiceInfoView();
  },

  members: {
    __service: null,
    __metadata: null,

    __createServiceInfoView: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(8).set({
        alignY: "middle"
      }));

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(8));
      hBox.add(this.__createThumbnail());
      hBox.add(this.__createExtraInfo(), {
        flex: 1
      });
      container.add(hBox);

      container.add(this.__createDescription());

      const rawMetadata = this.__createRawMetadata();
      const more = new qxapp.desktop.PanelView(this.tr("raw metadata"), rawMetadata).set({
        caretSize: 14
      });
      more.setCollapsed(true);
      more.getChildControl("title").setFont("text-12");
      container.add(more);

      this._add(container);
    },

    __createThumbnail: function() {
      return new qx.ui.basic.Image(this.__metadata.thumbnail || qxapp.utils.Utils.getThumbnailFromString(this.__metadata.key)).set({
        scale: true,
        width: 300,
        height: 180
      });
    },

    __createExtraInfo: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(8).set({
        alignY: "middle"
      }));
      container.add(this.__createTitle());
      container.add(this.__createContact());
      container.add(this.__createAuthors());
      const badges = this.__createBadges();
      if (badges) {
        container.add(badges);
      }
      return container;
    },

    __createTitle: function() {
      const titleContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const title = new qx.ui.basic.Label(this.__metadata.name).set({
        font: "title-16",
        rich: true
      });
      titleContainer.add(title);

      const version = new qx.ui.basic.Label("v" + this.__metadata.version).set({
        rich: true
      });
      titleContainer.add(version);

      return titleContainer;
    },

    __createContact: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      container.add(new qx.ui.basic.Label(this.tr("Contact")).set({
        font: "title-12"
      }));
      container.add(new qx.ui.basic.Label(this.__metadata.contact));
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
    },

    __createBadges: function() {
      const badges = new qxapp.ui.markdown.Markdown();
      if ("badges" in this.__metadata) {
        let markdown = "";
        for (let i in this.__metadata.badges) {
          const badge = this.__metadata.badges[i];
          markdown += `[![${badge.name}](${badge.image})](${badge.url}) `;
        }
        badges.setMarkdown(markdown);
        return badges;
      }
      return null;
    },

    __createDescription: function() {
      const description = new qxapp.ui.markdown.Markdown();
      description.setMarkdown(this.__metadata.description);
      return description;
    },

    __createRawMetadata: function() {
      const container = new qx.ui.container.Scroll();
      container.add(new qxapp.component.widget.JsonTreeWidget(this.__metadata, "serviceDescriptionSettings"));
      return container;
    },
  }
});
