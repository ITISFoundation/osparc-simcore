/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Preferences page for managing the user's tags.
 */
qx.Class.define("osparc.desktop.preferences.pages.TagsPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const studiesLabel = osparc.product.Utils.getStudyAlias({plural: true});
    const studyLabel = osparc.product.Utils.getStudyAlias();
    const msg = this.tr("\
    Tags help you organize the ") + studiesLabel + this.tr(" in the Dashboard by categorizing topics, making it easier to search and filter. \
    Once the tags are created, they can be assigned to the ") + studyLabel + this.tr("  via 'More options...' on the ") + studyLabel + this.tr(" cards.");
    const intro = osparc.ui.window.TabbedView.createHelpLabel(msg);
    this._add(intro);

    this._add(new qx.ui.core.Spacer(null, 10));

    this.__tagsContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__tagsContainer.set({
      paddingLeft: 10
    });
    const scroll = new qx.ui.container.Scroll(this.__tagsContainer);
    this._add(scroll, {
      flex: 1
    });

    this.__renderLayout();
  },

  members: {
    __tagsContainer: null,
    __addTagButton: null,

    __renderLayout: function() {
      const tags = osparc.store.Tags.getInstance().getTags();
      const tagItems = tags.map(tag => new osparc.form.tag.TagItem().set({tag}));
      tagItems.forEach(tagItem => {
        this.__tagsContainer.add(tagItem);
        this.__attachTagItemEvents(tagItem);
      });

      this.__addTagButton = new qx.ui.form.Button().set({
        appearance: "form-button-outlined",
        label: this.tr("New Tag"),
        icon: "@FontAwesome5Solid/plus/14"
      });
      osparc.utils.Utils.setIdToWidget(this.__addTagButton, "addTagBtn");
      this.__addTagButton.addListener("execute", () => {
        const newItem = new osparc.form.tag.TagItem().set({
          mode: osparc.form.tag.TagItem.modes.EDIT
        });
        this.__tagsContainer.add(newItem);
        this.__attachTagItemEvents(newItem);
      });

      // New tag button
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "center"
      }));
      buttonContainer.add(this.__addTagButton);
      this._add(buttonContainer);
    },

    __attachTagItemEvents: function(tagItem) {
      tagItem.addListener("cancelNewTag", e => this.__tagsContainer.remove(e.getTarget()), this);
      tagItem.addListener("deleteTag", e => this.__tagsContainer.remove(e.getTarget()));
    }
  }
});
