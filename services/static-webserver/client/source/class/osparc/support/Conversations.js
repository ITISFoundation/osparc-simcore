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


qx.Class.define("osparc.support.Conversations", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));
    this.__conversationListItems = [];

    this.__filterButtons = [];
    this.__filterButtons.push(this.getChildControl("filter-all-button"));
    this.__filterButtons.push(this.getChildControl("filter-unread-button"));
    /*
    if (osparc.store.Groups.getInstance().amIASupportUser()) {
      this.__filterButtons.push(this.getChildControl("filter-open-button"));
    }
    */

    this.__fetchConversations();

    this.__listenToNewConversations();
  },

  properties: {
    currentFilter: {
      check: [
        "all",
        "unread",
        "open",
      ],
      init: "all",
      event: "changeCurrentFilter",
    },
  },

  events: {
    "openConversation": "qx.event.type.Data",
  },

  statics: {
    FILTER_BUTTON_AESTHETIC: {
      appearance: "filter-toggle-button",
      allowGrowX: false,
      paddingTop: 4,
      paddingBottom: 4,
    },
  },

  members: {
    __conversationListItems: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "filters-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(4));
          this._addAt(control, 0);
          break;
        case "filter-all-button":
          control = new qx.ui.form.ToggleButton(this.tr("All"));
          control.set({
            value: true,
            toolTipText: this.tr("Show all conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => {
            this.setCurrentFilter("all");
            this.__applyCurrentFilter("all");
          });
          this.getChildControl("filters-layout").add(control);
          break;
        case "filter-unread-button":
          control = new qx.ui.form.ToggleButton(this.tr("Unread"));
          control.set({
            toolTipText: this.tr("Show only unread conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => {
            this.setCurrentFilter("unread");
            this.__applyCurrentFilter("unread");
          });
          this.getChildControl("filters-layout").add(control);
          break;
        case "filter-open-button":
          control = new qx.ui.form.ToggleButton(this.tr("Open"));
          control.set({
            toolTipText: this.tr("Show only open conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => {
            this.setCurrentFilter("open");
            this.__applyCurrentFilter("open");
          });
          this.getChildControl("filters-layout").add(control);
          break;
        case "loading-button":
          control = new osparc.ui.form.FetchButton();
          this._addAt(control, 1);
          break;
        case "no-messages-label":
          control = new qx.ui.basic.Label().set({
            alignX: "center",
            visibility: "excluded",
          });
          this._addAt(control, 2);
          break;
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._addAt(control, 3, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyCurrentFilter: function(filter) {
      this.getChildControl("no-messages-label").exclude();

      this.__filterButtons.forEach(button => {
        button.setValue(false);
      });
      switch (filter) {
        case "all":
          this.getChildControl("filter-all-button").setValue(true);
          break;
        case "unread":
          this.getChildControl("filter-unread-button").setValue(true);
          break;
        case "open":
          this.getChildControl("filter-open-button").setValue(true);
          break;
      }

      this.__conversationListItems.forEach(conversationItem => {
        const conversation = conversationItem.getConversation();
        switch (filter) {
          case "all":
            conversationItem.show();
            break;
          case "unread":
            if (osparc.store.Groups.getInstance().amIASupportUser()) {
              if (conversation.getReadBySupport()) {
                conversationItem.exclude();
              } else {
                conversationItem.show();
              }
            } else {
              if (conversation.getReadByUser()) {
                conversationItem.exclude();
              } else {
                conversationItem.show();
              }
            }
            break;
          case "open":
            if (conversation.getResolved() === false) {
              conversationItem.show();
            } else {
              conversationItem.exclude();
            }
            break;
        }
      });

      const hasVisibleConversations = this.__conversationListItems.some(conversationItem => conversationItem.isVisible());
      if (!hasVisibleConversations) {
        let msg = "";
        switch (filter) {
          case "all":
            msg = this.tr("No conversations yet");
            break;
          case "unread":
            msg = this.tr("No unread conversations");
            break;
          case "open":
            msg = this.tr("No open conversations");
            break;
        }
        this.getChildControl("no-messages-label").set({
          value: msg,
          visibility: "visible",
        });
      }
    },

    __getConversationItem: function(conversationId) {
      return this.__conversationListItems.find(conversation => conversation.getConversation().getConversationId() === conversationId);
    },

    __fetchConversations: function() {
      const loadMoreButton = this.getChildControl("loading-button");
      loadMoreButton.setFetching(true);

      osparc.store.ConversationsSupport.getInstance().fetchConversations()
        .then(conversations => {
          if (conversations.length) {
            conversations.forEach(conversation => this.__addConversation(conversation));
          }
          this.__sortConversations();
        })
        .finally(() => {
          loadMoreButton.setFetching(false);
          loadMoreButton.exclude();
          this.__applyCurrentFilter(this.getCurrentFilter());
        });
    },

    __listenToNewConversations: function() {
      osparc.store.ConversationsSupport.getInstance().addListener("conversationCreated", e => {
        const conversation = e.getData();
        this.__addConversation(conversation);
        this.__sortConversations();
      });
    },

    __addConversation: function(conversation) {
      // ignore it if it was already there
      const conversationId = conversation.getConversationId();
      const conversationItemFound = this.__getConversationItem(conversationId);
      if (conversationItemFound) {
        return null;
      }

      const conversationListItem = new osparc.support.ConversationListItem();
      conversationListItem.setConversation(conversation);
      conversationListItem.addListener("tap", () => this.fireDataEvent("openConversation", conversationId, this));
      conversation.addListener("changeModified", () => this.__sortConversations(), this);
      const eventName = osparc.store.Groups.getInstance().amIASupportUser() ? "changeReadBySupport" : "changeReadByUser";
      conversation.addListener(eventName, () => this.__applyCurrentFilter(this.getCurrentFilter()), this);
      conversation.addListener("changeResolved", () => this.__applyCurrentFilter(this.getCurrentFilter()), this);
      this.__conversationListItems.push(conversationListItem);
      return conversationListItem;
    },

    __sortConversations: function() {
      const conversationsLayout = this.getChildControl("conversations-layout");
      conversationsLayout.removeAll();
      // sort them by modified date (newest first)
      this.__conversationListItems.sort((a, b) => {
        const aDate = new Date(a.getConversation().getModified());
        const bDate = new Date(b.getConversation().getModified());
        return bDate - aDate;
      });
      this.__conversationListItems.forEach(item => conversationsLayout.add(item));
    },
  },
});
