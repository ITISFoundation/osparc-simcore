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

  construct: function(size = 32, orientation = "right", maxWidth = 150) {
    this.base(arguments);

    this.set({
      decorator: null,
      padding: 0,
      backgroundColor: null,
      width: maxWidth,
      maxWidth: maxWidth,
      allowGrowY: false,
    });
    this._setLayout(new qx.ui.layout.Canvas());

    this.__avatarSize = size;
    this.__orientation = orientation;
    this.__maxVisible = Math.max(1, Math.floor(maxWidth/size) - 1); // Ensure at least 1 visible avatar
    this.__userGroupIds = [];

    this.__isPointerInside = false;
    this.__onGlobalPointerMove = this.__onGlobalPointerMove.bind(this);
    document.addEventListener("pointermove", this.__onGlobalPointerMove);
  },

  members: {
    __avatarSize: null,
    __maxVisible: null,
    __userGroupIds: null,
    __avatars: null,
    __collapseTimeout: null,
    __isPointerInside: null,
    __onGlobalPointerMove: null,

    setUserGroupIds: function(userGroupIds) {
      if (JSON.stringify(userGroupIds) === JSON.stringify(this.__userGroupIds)) {
        return;
      }
      this.__userGroupIds = userGroupIds || [];
      const usersStore = osparc.store.Users.getInstance();
      const userPromises = userGroupIds.map(userGroupId => usersStore.getUser(userGroupId));
      const users = [];
      Promise.all(userPromises)
        .then(usersResult => {
          usersResult.forEach(user => {
            users.push({
              name: user.getUsername(),
              avatar: user.getThumbnail(),
            });
          });
          this.__buildAvatars(users);
        })
        .catch(error => {
          console.error("Failed to fetch user data for avatars:", error);
        });
    },

    __buildAvatars(users) {
      this._removeAll();
      this.__avatars = [];

      const usersToShow = users.slice(0, this.__maxVisible);
      const totalAvatars = [...usersToShow];
      if (users.length > this.__maxVisible) {
        totalAvatars.push({
          name: `+${users.length - this.__maxVisible}`,
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

    __onGlobalPointerMove(e) {
      const domEl = this.getContentElement().getDomElement();
      if (!domEl) {
        return;
      }

      const rect = domEl.getBoundingClientRect();
      const inside =
        e.clientX >= rect.left &&
        e.clientX <= rect.right &&
        e.clientY >= rect.top &&
        e.clientY <= rect.bottom;

      if (inside) {
        if (!this.__isPointerInside) {
          this.__isPointerInside = true;
          if (this.__collapseTimeout) {
            clearTimeout(this.__collapseTimeout);
            this.__collapseTimeout = null;
          }
          this.__expand(true);
        }
      } else {
        if (this.__isPointerInside) {
          this.__isPointerInside = false;
          if (this.__collapseTimeout) {
            clearTimeout(this.__collapseTimeout);
          }
          this.__collapseTimeout = setTimeout(() => {
            this.__expand(false);
          }, 200);
        }
      }
    }
  },

  destruct: function() {
    document.removeEventListener("pointermove", this.__onGlobalPointerMove);
  },
});
