/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Widget that displays the available information of the given service metadata.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *    const serviceDetails = new osparc.component.metadata.ServiceDetails(selectedService);
 *    this.add(serviceDetails);
 * </pre>
 */

qx.Class.define("osparc.component.metadata.ServiceDetails", {
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Service metadata
    */
  construct: function(serviceData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    this.set({
      service: serviceData,
      padding: 5,
      backgroundColor: "material-button-background"
    });
  },

  properties: {
    service: {
      check: "Object",
      nullable: false,
      apply: "_applyService",
      event: "changeService"
    }
  },

  members: {
    __detailsView: null,

    _applyService: function(service) {
      if (this.__detailsView) {
        this._remove(this.__detailsView);
      }

      if (service) {
        this.__createServiceDetailsView();
      }
    },

    __createServiceDetailsView: function() {
      const detailsView = this.__detailsView = new qx.ui.container.Composite(new qx.ui.layout.VBox(8).set({
        alignY: "middle"
      }));

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(8));
      hBox.add(this.__createExtraInfo());
      hBox.add(this.__createThumbnail(), {
        flex: 1
      });
      detailsView.add(hBox);

      detailsView.add(this.__createDescription());

      const rawMetadata = this.__createRawMetadata();
      const more = new osparc.desktop.PanelView(this.tr("raw metadata"), rawMetadata).set({
        caretSize: 14
      });
      more.setCollapsed(true);
      more.getChildControl("title").setFont("text-12");
      detailsView.add(more, {
        flex: 1
      });

      this._add(detailsView);
    },

    __createThumbnail: function() {
      return new osparc.component.widget.Thumbnail(this.getService().thumbnail || "@FontAwesome5Solid/flask/50", 300, 180);
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

      const title = new qx.ui.basic.Label(this.getService().name).set({
        font: "title-16",
        rich: true
      });
      titleContainer.add(title);

      const version = new qx.ui.basic.Label("v" + this.getService().version).set({
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
      container.add(new qx.ui.basic.Label(this.getService().contact));
      return container;
    },

    __createAuthors: function() {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      container.add(new qx.ui.basic.Label(this.tr("Authors")).set({
        font: "title-12"
      }));
      for (let i in this.getService().authors) {
        const author = this.getService().authors[i];
        const authorLine = `${author.name} · ${author.affiliation} · ${author.email}`;
        container.add(new qx.ui.basic.Label(authorLine));
      }
      return container;
    },

    __createBadges: function() {
      if ("badges" in this.getService()) {
        const badges = new osparc.ui.markdown.Markdown().set({
          noMargin: false
        });
        let markdown = "";
        for (let i in this.getService().badges) {
          const badge = this.getService().badges[i];
          markdown += `[![${badge.name}](${badge.image})](${badge.url}) `;
        }
        badges.setValue(markdown);
        return badges;
      }
      return null;
    },

    __createDescription: function() {
      const description = new osparc.ui.markdown.Markdown().set({
        noMargin: false
      });
      description.setValue(this.getService().description || "");
      return description;
    },

    __createRawMetadata: function() {
      const container = new qx.ui.container.Scroll();
      container.add(new osparc.ui.basic.JsonTreeWidget(this.getService(), "serviceDescriptionSettings"));
      return container;
    }
  }
});
