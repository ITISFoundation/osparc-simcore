/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.GridButtonNew", {
  extend: osparc.dashboard.GridButtonBase,

  construct: function(title, description) {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.NEW);

    this.set({
      appearance: "pb-new"
    });

    if (title) {
      title = osparc.utils.Utils.replaceTokens(
        title,
        "replace_me_product_name",
        osparc.store.StaticInfo.getInstance().getDisplayName()
      );

      const titleLabel = this.getChildControl("title");
      titleLabel.set({
        value: title,
        rich: true
      });
    }

    if (description) {
      description = osparc.utils.Utils.replaceTokens(
        description,
        "replace_me_product_name",
        osparc.store.StaticInfo.getInstance().getDisplayName()
      );

      const descLabel = this.getChildControl("subtitle-text");
      descLabel.setValue(description.toString());
    }

    this.setThumbnail(osparc.dashboard.CardBase.NEW_ICON);

    this.getChildControl("footer").exclude();
  },

  members: {
    _shouldApplyFilter: function(data) {
      return false;
    },

    _shouldReactToFilter: function(data) {
      return false;
    }
  }
});
