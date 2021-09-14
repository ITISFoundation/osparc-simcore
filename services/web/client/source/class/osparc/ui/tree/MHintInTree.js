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
      const texts = [];
      [
        this.getLabel(),
        this.getDescription(),
        this.getDescription2()
      ].forEach(text => {
        if (text && text !== "") {
          texts.push(text);
        }
      });
      const url = this.getUrl();
      if (url && url !== "") {
        const link = "<a href=" + url + " target='_blank'>More...</a>";
        const linkWithRightColor = link.replace(/^<a /, "<a style=\"color:"+ qx.theme.manager.Color.getInstance().getTheme().colors["link"] + "\"");
        texts.push(linkWithRightColor);

        const themeManager = qx.theme.manager.Meta.getInstance();
        themeManager.addListener("changeTheme", () => {
          this.__populateInfoButton();
        }, this);
      }
      const hint = texts.join("<br>");
      this.__infoButton.setHintText(hint);
    }
  }
});
