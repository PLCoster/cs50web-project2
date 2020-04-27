var socket;

document.addEventListener('DOMContentLoaded', () => {

  // Connect to websocket if not already connected:
  if (!io.connect().connected) {
    socket = io();
  }

  // SOCKET.IO Connection:
  socket.on('connect', () => {

    // Configure message input form, workspace and channel creation forms:
    message_config();
    new_channel_ws_config();
    logout_config();

    console.log('trying to join workspace')

    // Set up local storage via server:
    socket.emit('initial logon')

    // Connect user to their last workspace and channel:
    socket.emit('join workspace', {'sign in': true});
  });


  /*
  =============================================
  SOCKET IO FUNCTIONS
  =============================================
  */

  socket.on('local storage setup', data => {
    // On initial log on, set up local storage for app functionality:

    localStorage.setItem('user_id', data['user_id']);
  });

  socket.on('workspace logon', data => {
    // When a new workspace is joined, update workspace info:
    document.querySelector('#curr-workspace-show').innerHTML = data['workspace_name'] + ' \u23F7';
    document.querySelector('#curr-workspace-hide').innerHTML = data['workspace_name'] + ' \u23F6';
    document.querySelector('#curr-workspace').innerHTML = data['workspace_name'];
  });

  // When a new channel is joined, clear messages and display message history:
  socket.on('channel logon', data => {

    // Clear current messages
    document.querySelector('#messages').innerHTML = '';

    // Update current channel title
    document.querySelector('#curr-channel').innerHTML= data['channel_name'];

    // Add all message history:
    for (let i = 0; i < data['message_history'].length ; i++) {
      message = data['message_history'][i]
      post_message(message, false)
    }

    // Hide private chat:
    hide_private_chat();
  });


  // When a new private chat is joined, clear the private channel and display message history:
  socket.on('private logon', data => {

    // Clear current private messages
    document.querySelector('#private-messages').innerHTML = '';

    // Update current private chat name
    document.querySelector('#private-channel').innerHTML = data['channel_name'];

    // Add all message history:
    for (let i = 0; i < data['message_history'].length ; i++) {
      message = data['message_history'][i]
      post_message(message, true)
    }

    // Hide channel and show private messages:
    show_private_chat();
  });

  // When a new message is sent to the channel, add to the chat panel:
  socket.on('emit message', data => {
    console.log('Message received, message data:', data);
    if (data.private) {
      post_message(data['message'], true);
    } else {
      post_message(data['message'], false);
    }
  });

  // When a message is edited or deleted in the current channel, update message text:
  socket.on('emit edited message', data => {
    console.log('Message edit request received:', data);

    console.log('Private is: ', data.private, typeof data.private)

    let selector;

    if (!data.private) {
      selector = '#messages .user-message'
    } else {
      selector = '#private-messages .user-message'
    }

    // Select the correct message
    messages = document.querySelectorAll(selector);
    console.log('Messages selected:', messages)

    for (let i = 0; i < messages.length; i++) {
      if (messages[i].dataset.message_id == data.message_id && messages[i].dataset.timestamp == data.timestamp) {
        messages[i].querySelector('.message-text').innerHTML = data.edited_text;

        // If already edited, edit the text, else add edit text:
        if (messages[i].querySelector('.message-edited')) {
          messages[i].querySelector('.message-edited').innerHTML = data.edit_type + ' - ' + data.edit_date;
        } else {
          let edit = document.createElement('p');
          edit.classList.add('message-edited', 'text-muted');
          edit.innerHTML = data.edit_type + ' - ' + data.edit_date;
          messages[i].querySelector('.message-text').after(edit);
        }

        console.log(data.deleted)
        // If message is deleted, and own user message remove further editing options:
        if (data.deleted && messages[i].dataset.user_id === localStorage.getItem('user_id')) {
          messages[i].querySelector('.message-options').remove();
        }
        break;
      }
    }
  });

  // When a new workspace is added, update workspace links
  socket.on('workspace_list amended', data => {
    console.log('received updated workspace list');
    workspace_config(data.workspace_list);
  });

  // When a new channel is added, update channel links
  socket.on('channel_list amended', data => {
    console.log('received updated channel list')
    channel_config(data.channel_list);
  });

  // When a new private channel is added, private channel links
  socket.on('private_list amended', data => {
    console.log('received updated private list')
    private_config(data.priv_chan_list);
  });

  // When a user joins or leaves a ws, update number of live users in ws:
  socket.on('ws_users amended', data => {
    console.log('updated user number received: ', data.users);
    document.querySelector('#workspace-users').innerHTML = data.users;
    console.log(data.user_details)

    // Create message element using handlebars
    const template = Handlebars.compile(document.querySelector('#user-ws-template').innerHTML);

    const content = template({'user_details' : data.user_details});

    // Add to messages element
    document.querySelector('#workspace-users-list').innerHTML = content;
  });


  /*
  =============================================
  PAGE CONFIGURATION FUNCTIONS:
  =============================================
  */

  const message_config = function () {
    // Function to set up buttons to submit public messages to the server:
    document.querySelector('#send-chat-input').onclick = () => {
      event.preventDefault();

      // Hide any open message editor:
      document.querySelectorAll('.user-message').forEach( el => {
        el.querySelector('.message-edit-form').style.display = 'none';
        el.querySelector('.message-options').removeAttribute('style');
        el.querySelector('.message-text').style.display = 'block';
      })

      const message = document.querySelector('#message').value;
      console.log('Trying to send message to server:', message);
      if (message) {
        console.log('Sending Message: ', {'message': message});
        socket.emit('send message', {'message': message, 'private': false});
        document.querySelector('#message').value = '';
      }
    };

    // Function to set up buttons to submit private messages to the server:
    document.querySelector('#send-private-input').onclick = () => {
      event.preventDefault();

      // Hide any open message editors:
      document.querySelectorAll('.user-message').forEach( el => {
        el.querySelector('.message-edit-form').style.display = 'none';
        if (el.querySelector('.message-options')) {
          el.querySelector('.message-options').removeAttribute('style');
        }
        el.querySelector('.message-text').style.display = 'block';
      });

      const message = document.querySelector('#private-message').value;
      console.log('Trying to send private message to server:', message);
      if (message) {
        console.log('Sending Private Message: ', {'message': message});
        socket.emit('send message', {'message': message, 'private': true});
        document.querySelector('#private-message').value = '';
      }
    };
  };


  const workspace_config = function (ws_list) {
    // Function to set up links to change workspaces:

    // Remove current workspace list:
    document.querySelector('#workspace-links').innerHTML = '';

    // Add all WS Links:
    for (let i=0; i < ws_list.length; i++) {
      let ws_name = ws_list[i];

      const li = document.createElement('li');
      li.innerHTML = ws_name;
      li.className = 'ws-link';
      li.setAttribute('data-workspace', ws_name);
      li.setAttribute('href', '');

      document.querySelector('#workspace-links').append(li);
    }

    // Add onclick events to all Channel Links:
    document.querySelectorAll('.ws-link').forEach(button => {
      button.onclick = () => {
        event.preventDefault();
        console.log('You clicked on a workspace link!')
        socket.emit('join workspace', {'sign in': false, 'workspace': button.dataset.workspace});
        console.log('Workspace now set to: ', button.dataset.workspace);
      };
    });
  };

  const channel_config = function (channel_list) {
    // Function to set up links to change channels:

    // Remove current channel list:
    document.querySelector('#channel-links').innerHTML = '';

    // Add all Channel Links:
    for (let i=0; i < channel_list.length; i++) {
      let channel_name = channel_list[i];

      const li = document.createElement('li');
      li.innerHTML = channel_name;
      li.className = 'channel-link';
      li.setAttribute('data-channel', channel_name);
      li.setAttribute('href', '');

      document.querySelector('#channel-links').append(li);
    }

    // Add onclick events to all Channel Links:
    document.querySelectorAll('.channel-link').forEach(button => {
      button.onclick = () => {
        event.preventDefault();
        console.log('You clicked on a channel link!')
        socket.emit('join channel', {'channel': button.dataset.channel});
        console.log('Channel now set to: ', button.dataset.channel);
      };
    });
  };


  const private_config = function (private_list) {
    // Function to set up links for private channels:

    // Remove current channel list:
    document.querySelector('#private-links').innerHTML = '';

    // Add all Channel Links:
    for (let i=0; i < private_list.length; i++) {
      let user_id_1 = private_list[i][0];
      let user_id_2 = private_list[i][1];
      let private_name = private_list[i][2];

      const li = document.createElement('li');
      li.innerHTML = private_name;
      li.className = 'private-link';
      li.setAttribute('data-user_id_1', user_id_1);
      li.setAttribute('data-user_id_2', user_id_2);
      li.setAttribute('href', '');

      document.querySelector('#private-links').append(li);
    }

    // Add onclick events to all Channel Links:
    document.querySelectorAll('.private-link').forEach(button => {
      button.onclick = () => {
        event.preventDefault();
        console.log('You clicked on a private link!')
        socket.emit('join private', {'user_1': button.dataset.user_id_1, 'user_2': button.dataset.user_id_2});
      };
    });
  }


  const new_channel_ws_config = function () {
    // Function to set up form to create new channel in a workspace

    // Set up sidebar onclick display of channel creator:
    document.querySelector('#channel-options-display').onclick = function() {
      document.querySelector('#new-channel').style.display = 'block';
      document.querySelector('#channel-links').style.display = 'none';
      document.querySelector('#channel-options-hide').style.display = 'block';
      this.style.display = 'none';
      }

    // Set up sidebar hiding of channel creator form:
    document.querySelector('#channel-options-hide').onclick = function () {
      document.querySelector('#new-channel').style.display = 'none';
      document.querySelector('#channel-links').style.display = 'block';
      document.querySelector('#channel-options-display').style.display = 'block';
      this.style.display = 'none';
    }

    // Set up new channel creator form:
    document.querySelector('#new-channel>button').onclick = () => {
      event.preventDefault();
      const new_channel = document.querySelector('#channel-name').value;
      if (new_channel) {
        console.log('trying to create new channel: ', new_channel);
        socket.emit('create channel', {'new_channel': new_channel});
        document.querySelector('#channel-options-hide').click();
        document.querySelector('#channel-name').value = '';
      }
    };

    // Set up sidebar onclick display of workspace creator:
    document.querySelector('#workspace-options-display').onclick = function() {
      document.querySelector('#new-workspace').style.display = 'block';
      document.querySelector('#workspace-options-hide').style.display = 'block';
      document.querySelector('#curr-workspace-panel').style.display = 'none';
      this.style.display = 'none';
    };

    // Set up sidebar onclick hiding of workspace creator form:
    document.querySelector('#workspace-options-hide').onclick = function () {
      document.querySelector('#new-workspace').style.display = 'none';
      document.querySelector('#workspace-options-display').style.display = 'block';
      document.querySelector('#curr-workspace-panel').style.display = 'block';
      this.style.display = 'none';
    };

    // Set up clickable display of users workspaces:
    document.querySelector('#curr-workspace-show').onclick = function () {
      document.querySelector('#workspace-links').style.display = 'block';
      document.querySelector('#curr-workspace-hide').style.display = 'block';
      this.style.display = 'none';
    };

    // Set up clickable hiding of users workspaces:
    document.querySelector('#curr-workspace-hide').onclick = function () {
      document.querySelector('#workspace-links').style.display = 'none';
      document.querySelector('#curr-workspace-show').style.display = 'block';
      this.style.display = 'none';
    };

    // Set up new workspace creator form:
    document.querySelector('#new-workspace>button').onclick = () => {
      event.preventDefault();
      const new_ws = document.querySelector('#workspace-name').value;
      if (new_ws) {
        console.log('trying to create new workspace: ', new_ws);
        socket.emit('create workspace', {'new_workspace': new_ws});
        document.querySelector('#workspace-options-hide').click();
        document.querySelector('#workspace-name').value = '';
      }
    };
  };


  const logout_config = function () {
    // Function to configure log out button on chat screen

    document.querySelector('#logout').onclick = () => {
      event.preventDefault();
      socket.emit('log out');
      localStorage.clear();
      window.location.href = '/logout';
    };
  };
});


/*
  =============================================
  HELPER FUNCTIONS:
  =============================================
*/

const post_message = function (message, private) {
  // Helper function to post received messages to the chat panel

  let client_message, panel;

  // Check which panel to add messages to:
  if (private) {
    panel = '#private-messages'
  } else {
    panel = '#messages'
  }

  // Check if message is by the client or a different user:
  if (message.user_id === parseInt(localStorage.getItem('user_id'))) {
    client_message = true;
  } else {
    client_message = false;
  }

  // Create message element using handlebars
  const template = Handlebars.compile(document.querySelector('#message-template').innerHTML);

  const content = template({'message' : message, 'client_message' : client_message});

  // Add to messages element
  document.querySelector(panel).innerHTML += content;
};

const private_message = function() {
  // Helper function to create and join private chat with a specific user

  event.preventDefault();

  let target_id = event.target.dataset.target_id;

  let user_id = localStorage.getItem('user_id');

  console.log('trying to start private chat');
  console.log('between users: ', user_id, target_id);

  socket.emit('create private channel', {'target_id': target_id, 'user_id': user_id})
};


const delete_message = function () {
  // Helper function to delete a clients own message from a chat page

  event.preventDefault();

  let message = event.target;
  let message_id = message.dataset.message_id;
  let timestamp = message.dataset.timestamp;
  let private = (message.dataset.private === 'true');

  console.log('Deleting message: ', message_id, timestamp);

  socket.emit('delete message', {'message_id': message_id, 'timestamp': timestamp, 'private': private});
};

const message_editor = function () {
  // Helper function to open message editing form when edit button clicked

  event.preventDefault();

  let message = event.target;
  let message_id = message.dataset.message_id;
  let timestamp = message.dataset.timestamp;
  let private = (message.dataset.private === 'true');

  // Select the correct message and display the message editor form:
  messages = document.querySelectorAll('.user-message');

  for (let i = 0; i < messages.length; i++) {
    if (messages[i].dataset.message_id == message_id && messages[i].dataset.timestamp == timestamp) {
      let message = messages[i]

      console.log('Trying to Edit Message')

      message_text = message.querySelector('.message-text').innerHTML;

      console.log('Message Text to Edit:', message_text);
      message.querySelector('.message-edit').value = message_text;
      message.querySelector('.message-options').style.display = 'none';
      message.querySelector('.message-text').style.display = 'none';
      message.querySelector('.message-edit-form').style.display = 'block';

      // Set edit message button functionality:
      message.querySelector('.edit-message').addEventListener("click", function () {
        event.preventDefault();

        let edited = message.querySelector('.message-edit').value;

        // If there is edited message text, send message and hide the form:
        if (edited && edited !== message_text) {
          console.log('Editing message:', edited)
          socket.emit('edit message', {'message_id': message_id, 'timestamp': timestamp, 'message_text': edited, 'private': private});
          message.querySelector('.cancel-edit').click();
        }
      });

      // Set cancel editing button functionality:
      message.querySelector('.cancel-edit').addEventListener("click", function () {
        event.preventDefault();
        message.querySelector('.message-options').removeAttribute('style');
        message.querySelector('.message-text').style.display = 'block';
        message.querySelector('.message-edit-form').style.display = 'none';
      });

      break;
    }
  }
};

const show_private_chat = function () {
  // Opens private chat window, header and input
  document.querySelector('#private-panel').style.display = 'block';
  document.querySelector('#private-panel').style.opacity = '1';
  document.querySelector('#chatroom-panel').style.display = 'none';
};

const hide_private_chat = function () {
  // Closes private chat window, header and input
  document.querySelector('#private-panel').style.display = 'none';
  document.querySelector('#private-panel').style.opacity = '0';
  document.querySelector('#chatroom-panel').style.display = 'block';
};

const show_ws_users = function () {
  // Slides out workspace users panel
  let panel = document.querySelector('#workspace-user-panel');
  panel.style.width = '250px';
  panel.style.opacity = '1';
  panel.style.paddingLeft = '20px';
};

const hide_ws_users = function () {
  // Hides workspace users panel
  let panel = document.querySelector('#workspace-user-panel')
  panel.removeAttribute('style');
  panel.style.paddingLeft = '0';
};