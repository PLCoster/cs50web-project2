document.addEventListener('DOMContentLoaded', () => {

  let screen_name, channel;

  // Connect to websocket if not already connected:
  if (!io.connect().connected) {
    var socket = io();
  }

  // When socket is connected, run script:
  socket.on('connect', () => {

    // Function to set up sending messages to the server:
    const message_config = function () {
      // Each button should emit a "submit vote" event
      document.querySelectorAll('#vote > button').forEach(button => {
        button.onclick = () => {
            event.preventDefault();
            const message = document.querySelector('#message').value;
            if (message) {
              socket.emit('send message', {'message': message, 'screen_name': screen_name});
              document.querySelector('#message').value = '';
            }
        };
      });
    };

    // Log in form should set username and then hide login and display vote buttons
    // Only visible if there is no username in local storage
    document.querySelector('#login').onsubmit = () => {
      event.preventDefault();
      if (document.querySelector('#login-screen_name').value) {
        localStorage.setItem('screen_name', document.querySelector('#login-screen_name').value);
        screen_name = localStorage.getItem('screen_name');
        message_config();

        // Hide Login Form and Reveal Vote Buttons:
        document.querySelector('#login').style.display = "none";
        document.querySelector('#vote').style.display = "inline";
        }
      };

    // Check local storage for username, channel or subchannel if none, ask for a username:
    if (!localStorage.getItem('screen_name')) {
      document.querySelector('#login').style.display = "block";
      document.querySelector('#vote').style.display = "none";
      channel = 'Home';
    } else {
      screen_name = localStorage.getItem('screen_name');
      channel = localStorage.getItem('channel') || 'Home';
      document.querySelector('#login').style.display = "none";
      message_config();
    }

    // Connect to the last saved channel or the home channel if none saved:
    socket.emit("join channel", {"channel": channel});

    // When a new channel is joined, clear messages and display message history:
    socket.on('channel logon', data => {
      // Clear current messages
      document.querySelector('#votes').innerHTML = '';

      console.log('Getting message history...', data['message_history'])

      // Add all new messages:
      for (let i = 0; i < data['message_history'].length ; i++) {
        message = data['message_history'][i]

        // Create message li
        const li = document.createElement('li');
        li.innerHTML = `${message[1]}'s says: ${message[0]} - Posted ${message[3]} - `;

        // Create message date span
        const dateSpan = document.createElement('span');
        dateSpan.setAttribute('data-livestamp', message[2]);
        li.appendChild(dateSpan);

        // Add to messages element
        document.querySelector('#votes').append(li);
      }
    })

    // When a new vote is announced, add to the unordered list
    socket.on('announce vote', data => {
      console.log('vote broadcast received, vote data:', data);

      // Create message li
      const li = document.createElement('li');
      li.innerHTML = `${data.message[1]}'s says: ${data.message[0]} - Posted ${data.message[3]} - `;

      // Create message date span
      const dateSpan = document.createElement('span');
      dateSpan.setAttribute('data-livestamp', data.message[2]);
      li.appendChild(dateSpan);

      // Add to messages element
      document.querySelector('#votes').append(li);

    });
  });
});