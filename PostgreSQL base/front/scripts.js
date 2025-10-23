    const loginContainer = document.getElementById('login-container');
    const adminPanel = document.getElementById('admin-panel');
    const loginForm = document.getElementById('login-form');
    const logoutBtn = document.getElementById('logout-btn');
    const skuTable = document.getElementById('sku-table');
    const tableBody = document.getElementById('table-body');
    const addBtn = document.getElementById('add-btn');

    let token = localStorage.getItem('token');

    function decodeJWT(token) {
        const payload = token.split('.')[1];
        const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
        return decoded;
    }

    if (token) {
        try {
            const decoded = decodeJWT(token);
            if (decoded.role === 'superuser' && decoded.exp * 1000 > Date.now()) {
                showAdminPanel();
                loadData();
            } else {
                showLogin();
            }
        } catch {
            showLogin();
        }
    } else {
        showLogin();
    }

    function showLogin() {
        loginContainer.classList.remove('hidden');
        adminPanel.classList.add('hidden');
    }

    function showAdminPanel() {
        loginContainer.classList.add('hidden');
        adminPanel.classList.remove('hidden');
    }

    // Обработка логина
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        try {
            const response = await fetch('/login', {  // Заменить на полный URL бэкенда, 'http://localhost:5000/login'
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            if (response.ok) {
                const data = await response.json();
                token = data.token;
                localStorage.setItem('token', token);
                const decoded = decodeJWT(token);
                if (decoded.role === 'superuser') {
                    showAdminPanel();
                    loadData();
                } else {
                    alert('Доступ только для суперюзера.');
                }
            } else {
                alert('Неверные данные доступа.');
            }
        } catch (error) {
            alert('Ошибка сети. Проверь подключение к бэкенду.');
        }
    });

    logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('token');
        token = null;
        showLogin();
    });

    async function loadData() {
        try {
            const response = await fetch('/sku', {  // Заменить на полный URL бэкенда, 'http://localhost:5000/sku'
                headers: { 'Authorization': 'Bearer ' + token }
            });
            if (response.ok) {
                const data = await response.json();
                renderTable(data);
            } else {
                alert('Ошибка загрузки данных. Проверь токен.');
            }
        } catch (error) {
            alert('Ошибка сети. Проверь подключение к бэкенду.');
        }
    }

    function renderTable(data) {
        tableBody.innerHTML = '';
        data.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="text" value="${item.sku}" class="form-control" data-field="sku" data-id="${item.id}"></td>
                <td><input type="number" value="${item.plan_margin}" class="form-control" data-field="plan_margin" data-id="${item.id}"></td>
                <td><input type="number" value="${item.plan_orders}" class="form-control" data-field="plan_orders" data-id="${item.id}"></td>
                <!-- Добавь другие поля из твоего примера: например, <td><input value="${item.остатки}" data-field="остатки" data-id="${item.id}"></td> -->
                <td>
                    <button class="btn-primary save-btn" data-id="${item.id}">Сохранить</button>
                    <button class="btn-danger delete-btn" data-id="${item.id}">Удалить</button>
                </td>
            `;
            tableBody.appendChild(row);
        });

        document.querySelectorAll('.save-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.id;
                const row = btn.closest('tr');
                const updatedData = {};
                row.querySelectorAll('input[data-field]').forEach(input => {
                    updatedData[input.dataset.field] = input.type === 'number' ? +input.value : input.value;
                });

                try {
                    const response = await fetch(`/sku/${id}`, {  // Заменить на полный URL бэкенда, 'http://localhost:5000/sku/${id}'
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer ' + token
                        },
                        body: JSON.stringify(updatedData)
                    });
                    if (response.ok) {
                        loadData();  // Перезагрузка показанных данных
                    } else {
                        alert('Ошибка сохранения изменений.');
                    }
                } catch (error) {
                    alert('Ошибка сети.');
                }
            });
        });

        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (confirm('Удалить эту запись?')) {
                    const id = btn.dataset.id;
                    try {
                        const response = await fetch(`/sku/${id}`, {  // Заменить на полный URL бэкенда, 'http://localhost:5000/sku/${id}'
                            method: 'DELETE',
                            headers: { 'Authorization': 'Bearer ' + token }
                        });
                        if (response.ok) {
                            loadData();
                        } else {
                            alert('Ошибка удаления.');
                        }
                    } catch (error) {
                        alert('Ошибка сети.');
                    }
                }
            });
        });
    }

    addBtn.addEventListener('click', async () => {
        const newSku = document.getElementById('new-sku').value;
        const newMargin = +document.getElementById('new-margin').value;
        const newOrders = +document.getElementById('new-orders').value;
        // Можно добавить здесь другие поля из формы по типу: const newOstatki = document.getElementById('new-ostatki').value;

        if (!newSku || !newMargin || !newOrders) {
            alert('Пожалуйста, заполни все обязательные поля.');
            return;
        }

        const newData = { sku: newSku, plan_margin: newMargin, plan_orders: newOrders };

        try {
            const response = await fetch('/sku', {  // Заменить на полный URL бэкенда, 'http://localhost:5000/sku'
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify(newData)
            });
            if (response.ok) {
                loadData();
                document.getElementById('new-sku').value = '';
                document.getElementById('new-margin').value = '';
                document.getElementById('new-orders').value = '';
            } else {
                alert('Ошибка добавления записи.');
            }
        } catch (error) {
            alert('Ошибка сети.');
        }
    });
