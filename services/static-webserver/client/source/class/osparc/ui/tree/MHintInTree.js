/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Mixin.define("osparc.ui.tree.MHintInTree", {
  properties: {
    description: {
      check: "String",
      init: null,
      event: "changeDescription",
      apply: "__populateInfoButton",
      nullable: true
    },

    description2: {
      check: "String",
      init: null,
      event: "changeDescription2",
      apply: "__populateInfoButton",
      nullable: true
    },

    url: {
      check: "String",
      init: null,
      event: "changeUrl",
      apply: "__populateInfoButton",
      nullable: true
    }
  },

  members: {
    addHint: function() {
      this.__infoButton = new osparc.ui.hint.InfoHint();
      this._add(this.__infoButton);

      return this.__infoButton;
    },

    __populateInfoButton: function() {
      const desc = this.getDescription();
      const desc2 = this.getDescription2();
      const url = this.getUrl();
      const hints = [];
      if (desc && desc !== "") {
        hints.push(desc);
      }
      if (desc2 && desc2 !== "") {
        hints.push(desc2);
      }
      if (url && url !== "") {
        const link = "<a href=" + url + " target='_blank'>More...</a>";
        const linkWithRightColor = link.replace(/^<a /, "<a style=\"color:"+ qx.theme.manager.Color.getInstance().getTheme().colors["link"] + "\"");
        hints.push(linkWithRightColor);

        const themeManager = qx.theme.manager.Meta.getInstance();
        themeManager.addListener("changeTheme", () => {
          this.__populateInfoButton();
        }, this);
      }
      const hint = hints.join("<br>");
      this.__infoButton.setHintText(hint);
    }
  }
});
