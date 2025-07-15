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

  construct: function() {
    this.base(arguments);

    this.set({
      decorator: null,
      padding: 0,
      backgroundColor: null,
    });
    this._setLayout(new qx.ui.layout.Canvas());

    this.__avatarSize = 30;
    this.__maxVisible = 5;
    this.__users = [
      { name: "Alice", avatar: "https://i.pravatar.cc/150?img=1" },
      { name: "Bob", avatar: "https://i.pravatar.cc/150?img=2" },
      { name: "Charlie", avatar: "https://i.pravatar.cc/150?img=3" },
      { name: "Dana", avatar: "https://i.pravatar.cc/150?img=4" },
      { name: "Eve", avatar: "https://i.pravatar.cc/150?img=5" },
      { name: "Frank", avatar: "https://i.pravatar.cc/150?img=6" },
    ];
    this.__avatars = [];

    this.__buildAvatars();

    // Hover state handling
    this.addListener("mouseover", this.__expand, this);
    this.addListener("mouseout", this.__collapse, this);
  },

  members: {
    __avatarSize: null,
    __maxVisible: null,
    __users: null,
    __avatars: null,

    __buildAvatars() {
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
            backgroundColor: "#ddd",
            font: "bold",
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

        avatar.getContentElement().setStyles({
          borderRadius: "50%",
          border: "1px solid gray",
          boxShadow: "0 0 0 1px rgba(0,0,0,0.1)",
          transition: "left 0.2s ease",
          position: "absolute"
        });

        this.__avatars.push(avatar);
        this._add(avatar);
      });

      this.__collapse();
    },


    __expand() {
      const spacing = 8;
      this.__avatars.forEach((avatar, index) => {
        const left = index * (this.__avatarSize + spacing);
        avatar.setLayoutProperties({ left });
        avatar.setZIndex(this.__avatars.length - index); // reverse stacking
      });
    },

    __collapse() {
      const overlap = Math.floor(this.__avatarSize * 0.8);
      this.__avatars.forEach((avatar, index) => {
        const left = index * (this.__avatarSize - overlap);
        avatar.setLayoutProperties({ left });
        avatar.setZIndex(index); // natural stacking
      });
    },
  },
});
