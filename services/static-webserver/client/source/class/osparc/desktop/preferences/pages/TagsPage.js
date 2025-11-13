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
    const intro = new qx.ui.basic.Label(msg).set({
      font: "text-13",
      rich: true,
      wrap: true
    });
    this._add(intro);

    this.__renderLayout();
  },

  members: {
    __tagsContainer: null,

    __renderLayout: async function() {
      // Tags
      this.__tagsContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));
      this.__tagsContainer.set({
        paddingLeft: 10
      });
      const tagContainerScroll = new qx.ui.container.Scroll(this.__tagsContainer);
      this._add(tagContainerScroll, {
        flex: 1
      });

      const tags = osparc.store.Tags.getInstance().getTags();
      for (const tag of tags) {
        await osparc.store.Tags.getInstance().fetchAccessRights(tag);
      }
      const tagItems = tags.map(tag => {
        const tagItem = new osparc.form.tag.TagItem().set({
          tag
        });
        tagItem.getChildControl("tag").set({
          font: "text-12"
        });
        return tagItem;
      });
      tagItems.forEach(tagItem => {
        this.__tagsContainer.add(tagItem);
        this.__attachTagItemEvents(tagItem);
      });

      // New tag Button
      const addTagButton = new qx.ui.form.Button().set({
        appearance: "form-button-outlined",
        label: this.tr("New Tag"),
        icon: "@FontAwesome5Solid/plus/14"
      });
      osparc.utils.Utils.setIdToWidget(addTagButton, "addTagBtn");
      addTagButton.addListener("execute", () => {
        const newItem = new osparc.form.tag.TagItem().set({
          mode: osparc.form.tag.TagItem.modes.EDIT
        });
        this.__tagsContainer.add(newItem);
        this.__attachTagItemEvents(newItem);

        // scroll down
        const height = tagContainerScroll.getSizeHint().height;
        tagContainerScroll.scrollToY(height);
      });

      // New tag button
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "center"
      }));
      buttonContainer.add(addTagButton);
      this._add(buttonContainer);
    },

    __attachTagItemEvents: function(tagItem) {
      tagItem.addListener("cancelNewTag", e => this.__tagsContainer.remove(e.getTarget()), this);
      tagItem.addListener("deleteTag", e => this.__tagsContainer.remove(e.getTarget()));
    }
  }
});
