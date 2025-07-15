/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.ui.basic.AvatarGroup", {
  extend: qx.ui.core.Widget,

  construct: function(size = 30, orientation = "left", maxWidth = 150) {
    this.base(arguments);

    this.set({
      decorator: null,
      padding: 0,
      backgroundColor: null,
      width: maxWidth,
      maxWidth: maxWidth,
    });
    this._setLayout(new qx.ui.layout.Canvas());

    this.__avatarSize = size;
    this.__orientation = orientation;
    this.__maxVisible = Math.floor(maxWidth/size) - 1; // Reserve space for the extra avatar

    // Hover state handling
    this.addListener("pointerover", () => {
      if (this.__collapseTimeout) {
        clearTimeout(this.__collapseTimeout);
        this.__collapseTimeout = null;
      }
      this.__expand(true);
    }, this);

    this.addListener("pointerout", () => {
      this.__collapseTimeout = setTimeout(() => {
        this.__expand(false);
      }, 200); // short delay to avoid tooltip flicker collapse
    }, this);
  },

  members: {
    __avatarSize: null,
    __maxVisible: null,
    __users: null,
    __avatars: null,
    __collapseTimeout: null,

    setUsers: function(users) {
      this.__users = users;
      this.__buildAvatars();
    },

    __buildAvatars() {
      this._removeAll();
      this.__avatars = [];

      const usersToShow = this.__users.slice(0, this.__maxVisible);
      const totalAvatars = [...usersToShow];
      if (this.__users.length > this.__maxVisible) {
        totalAvatars.push({
          name: `+${this.__users.length - this.__maxVisible}`,
          isExtra: true
        });
      }

      totalAvatars.forEach(user => {
        let avatar;

        if (user.isExtra) {
          avatar = new qx.ui.basic.Label(user.name);
          avatar.set({
            width: this.__avatarSize,
            height: this.__avatarSize,
            textAlign: "center",
            backgroundColor: "text",
            textColor: "text-complementary",
            toolTipText: `${user.name.replace("+", "")} more`
          });

          avatar.getContentElement().setStyles({
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            fontWeight: "bold",
            fontSize: "0.8em"
          });
        } else {
          avatar = new qx.ui.basic.Image(user.avatar);
          avatar.set({
            width: this.__avatarSize,
            height: this.__avatarSize,
            scale: true,
            toolTipText: user.name
          });
        }

        const haloColor = qx.theme.manager.Color.getInstance().resolve("text");
        avatar.getContentElement().setStyles({
          borderRadius: "50%",
          border: "1px solid " + haloColor,
          boxShadow: "0 0 0 1px rgba(0,0,0,0.1)",
          transition: "left 0.1s ease, right 0.1s ease",
          position: "absolute"
        });

        this.__avatars.push(avatar);
        this._add(avatar);
      });

      this.__expand(false);
    },


    __expand: function(expand = true) {
      const overlap = Math.floor(this.__avatarSize * (expand ? 0.1 : 0.7));
      this.__avatars.forEach((avatar, index) => {
        const shift = index * (this.__avatarSize - overlap);
        avatar.setLayoutProperties({
          [this.__orientation]: shift
        });
        avatar.setZIndex(index);
      });
    },
  },
});
