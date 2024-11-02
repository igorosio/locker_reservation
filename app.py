import random
import datetime
import sqlite3
import hashlib
import re

# Funzione per inizializzare il database
def init_db():
    conn = sqlite3.connect('smart_locker.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prenotazioni (
            pin TEXT PRIMARY KEY,
            nome TEXT,
            email TEXT,
            tipo TEXT,
            data_inizio TEXT,
            data_fine TEXT,
            box TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stato_box (
            box TEXT PRIMARY KEY,
            stato TEXT,
            board INTEGER,
            port INTEGER
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM stato_box")
    if cursor.fetchone()[0] == 0:
        for t, n in zip(["p", "m", "g"], [3, 3, 3]):
            for i in range(1, n + 1):
                board = random.randint(1, 10)
                port = random.randint(1, 10)
                cursor.execute("INSERT INTO stato_box VALUES (?, ?, ?, ?)", (f"{i}{t}", "Libero", board, port))

    conn.commit()
    return conn, cursor

conn, cursor = init_db()

def genera_pin():
    while True:
        pin = random.sample("0123456789", 8)
        pin = "".join(pin)
        if not any(pin[i] == pin[i+1] for i in range(7)):
            return pin

def mostra_disponibilita():
    print("\nDisponibilità box:")
    for tipo in ["p", "m", "g"]:
        cursor.execute("SELECT COUNT(*) FROM stato_box WHERE stato = 'Libero' AND box LIKE ?", (f"%{tipo}",))
        disponibili = cursor.fetchone()[0]
        print(f"- {tipo.upper()}: {disponibili} disponibili")

def mostra_box_liberi():
    print("\nBox liberi:")
    cursor.execute("SELECT box, board, port FROM stato_box WHERE stato = 'Libero'")
    box_liberi = cursor.fetchall()
    if box_liberi:
        for box, board, port in box_liberi:
            print(f"- Box: {box}, Board: {board}, Port: {port}")
    else:
        print("Non ci sono box liberi al momento.")

def valida_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

def prenota_box():
    try:
        mostra_disponibilita()

        nome = input("Inserisci il tuo nome: ")
        email = input("Inserisci la tua email: ")

        if not valida_email(email):
            print("Email non valida. Riprova.")
            return

        tipo = input("Scegli il tipo di box (Piccolo (P), Medio (M), Grande (G)): ").lower()[0]

        while True:
            try:
                giorno = int(input("Inserisci il giorno (1-31): "))
                mese = int(input("Inserisci il mese (1-12): "))
                anno = int(input("Inserisci l'anno: "))
                ora_inizio = int(input("Inserisci l'ora di inizio (0-23): "))
                durata = int(input("Inserisci la durata della prenotazione in ore: "))
                data_inizio = datetime.datetime(anno, mese, giorno, ora_inizio)
                data_fine = data_inizio + datetime.timedelta(hours=durata)

                if data_inizio < datetime.datetime.now():
                    print("Data e ora non valide. Devi scegliere una data futura.")
                else:
                    break  # Esci dal ciclo se la data è valida
            except ValueError:
                print("Data o durata non valida. Riprova.")

        cursor.execute("SELECT box FROM stato_box WHERE stato = 'Libero' AND box LIKE ?", (f"%{tipo}",))
        box_disponibili = [row[0] for row in cursor.fetchall()]
        if not box_disponibili:
            print(f"Nessun box disponibile di tipo {tipo.upper()} a quella data e ora.")
            return

        # Genera un PIN univoco e memorizza la prenotazione con hash
        pin = genera_pin()
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        nome_hash = hashlib.sha256(nome.encode()).hexdigest()
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        box_assegnato = box_disponibili[0]

        cursor.execute("INSERT INTO prenotazioni VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (pin_hash, nome_hash, email_hash, tipo, data_inizio.isoformat(), data_fine.isoformat(), box_assegnato))
        cursor.execute("UPDATE stato_box SET stato = 'Prenotato' WHERE box = ?", (box_assegnato,))
        conn.commit()

        cursor.execute("SELECT board, port FROM stato_box WHERE box = ?", (box_assegnato,))
        board, port = cursor.fetchone()

        print(f"\nPrenotazione effettuata! Il tuo PIN è: {pin}, il tuo box è: {box_assegnato} (board: {board}, port: {port})")
        log_azione(f"Prenotazione: PIN={pin}, Nome={nome}, Email={email}, Box={box_assegnato}, Board={board}, Port={port}, Data Inizio={data_inizio}, Data Fine={data_fine}")
    except sqlite3.Error as e:
        print(f"Errore nel database: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Errore: {e}")

def deposita_oggetto():
    try:
        pin = input("Inserisci il tuo PIN: ")
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        cursor.execute("SELECT data_inizio, box FROM prenotazioni WHERE pin = ?", (pin_hash,))
        result = cursor.fetchone()
        if result:
            data_inizio, box_assegnato = result
            data_inizio = datetime.datetime.fromisoformat(data_inizio)
            if datetime.datetime.now() < data_inizio:
                print("Non è possibile depositare l'oggetto prima dell'orario di inizio della prenotazione.")
                return

            if cursor.execute("SELECT stato FROM stato_box WHERE box = ?", (box_assegnato,)).fetchone()[0] == "Prenotato":
                cursor.execute("UPDATE stato_box SET stato = 'Pieno' WHERE box = ?", (box_assegnato,))
                conn.commit()
                print("Oggetto depositato con successo!")
                log_azione(f"Deposito: PIN={pin}, Box={box_assegnato}")
            else:
                print("Il box non è nello stato corretto per il deposito.")
        else:
            print("PIN non valido.")
    except sqlite3.Error as e:
        print(f"Errore nel database: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Errore: {e}")

def ritira_oggetto():
    try:
        pin = input("Inserisci il tuo PIN: ")
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        if pin_hash in [p[0] for p in cursor.execute("SELECT pin FROM prenotazioni").fetchall()]:
            cursor.execute("SELECT box FROM prenotazioni WHERE pin = ?", (pin_hash,))
            box_assegnato = cursor.fetchone()[0]
            if cursor.execute("SELECT stato FROM stato_box WHERE box = ?", (box_assegnato,)).fetchone()[0] == "Pieno":
                scelta = input("Ritiro definitivo (D) o temporaneo (T)? ").upper()
                if scelta == "D":
                    cursor.execute("UPDATE stato_box SET stato = 'Libero' WHERE box = ?", (box_assegnato,))
                    cursor.execute("DELETE FROM prenotazioni WHERE pin = ?", (pin_hash,))
                    conn.commit()
                    print("Oggetto ritirato e prenotazione cancellata.")
                    log_azione(f"Ritiro Definitivo: PIN={pin}, Box={box_assegnato}")
                elif scelta == "T":
                    print("Oggetto ritirato temporaneamente.")
                    log_azione(f"Ritiro Temporaneo: PIN={pin}, Box={box_assegnato}")
                else:
                    print("Scelta non valida.")
            else:
                print("Il box non è nello stato corretto per il ritiro.")
        else:
            print("PIN non valido.")
    except sqlite3.Error as e:
        print(f"Errore nel database: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Errore: {e}")

def visualizza_box_prenotati_deposito():
    try:
        cursor.execute("SELECT box, stato FROM stato_box WHERE stato = 'Prenotato' OR stato = 'Pieno'")
        box_prenotati_deposito = cursor.fetchall()
        if box_prenotati_deposito:
            print("\nBox prenotati e con deposito:")
            for box, stato in box_prenotati_deposito:
                print(f"- Box: {box}, Stato: {stato}")
        else:
            print("Non ci sono box prenotati o con deposito.")
    except sqlite3.Error as e:
        print(f"Errore nel database: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Errore: {e}")

def gestisci_prenotazione():
    try:
        pin = input("Inserisci il tuo PIN: ")
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        email = input("Inserisci la tua email: ")
        email_hash = hashlib.sha256(email.encode()).hexdigest()

        cursor.execute("SELECT * FROM prenotazioni WHERE pin = ? AND email = ?", (pin_hash, email_hash))
        prenotazione = cursor.fetchone()

        if prenotazione:
            print("\nPrenotazione trovata:")
            print(f"- PIN: {pin}")
            print(f"- Nome: {hashlib.sha256(prenotazione[1].encode()).hexdigest()}")
            print(f"- Email: {hashlib.sha256(prenotazione[2].encode()).hexdigest()}")
            print(f"- Tipo: {prenotazione[3]}")
            print(f"- Data Inizio: {prenotazione[4]}")
            print(f"- Data Fine: {prenotazione[5]}")
            print(f"- Box: {prenotazione[6]}")

            scelta = input("\nCosa vuoi fare? (C)ancella, (M)odifica o (N)iente: ").upper()
            if scelta == "C":
                cursor.execute("DELETE FROM prenotazioni WHERE pin = ? AND email = ?", (pin_hash, email_hash))
                cursor.execute("UPDATE stato_box SET stato = 'Libero' WHERE box = ?", (prenotazione[6],))
                conn.commit()
                print("Prenotazione cancellata con successo!")
                log_azione(f"Cancellazione Prenotazione: PIN={pin}, Email={email}")
            elif scelta == "M":
                mostra_disponibilita()

                tipo = input("Scegli il nuovo tipo di box (Piccolo (P), Medio (M), Grande (G)): ").lower()[0]

                while True:
                    try:
                        giorno = int(input("Inserisci il nuovo giorno (1-31): "))
                        mese = int(input("Inserisci il nuovo mese (1-12): "))
                        anno = int(input("Inserisci il nuovo anno: "))
                        ora_inizio = int(input("Inserisci la nuova ora di inizio (0-23): "))
                        durata = int(input("Inserisci la nuova durata della prenotazione in ore: "))
                        data_inizio = datetime.datetime(anno, mese, giorno, ora_inizio)
                        data_fine = data_inizio + datetime.timedelta(hours=durata)

                        if data_inizio < datetime.datetime.now():
                            print("Data e ora non valide. Devi scegliere una data futura.")
                        else:
                            break  # Esci dal ciclo se la data è valida
                    except ValueError:
                        print("Data o durata non valida. Riprova.")

                cursor.execute("SELECT box FROM stato_box WHERE stato = 'Libero' AND box LIKE ?", (f"%{tipo}",))
                box_disponibili = [row[0] for row in cursor.fetchall()]
                if not box_disponibili:
                    print(f"Nessun box disponibile di tipo {tipo.upper()} a quella data e ora.")
                    return

                box_assegnato = box_disponibili[0]

                cursor.execute("UPDATE prenotazioni SET tipo = ?, data_inizio = ?, data_fine = ?, box = ? WHERE pin = ? AND email = ?",
                               (tipo, data_inizio.isoformat(), data_fine.isoformat(), box_assegnato, pin_hash, email_hash))
                cursor.execute("UPDATE stato_box SET stato = 'Prenotato' WHERE box = ?", (box_assegnato,))
                cursor.execute("UPDATE stato_box SET stato = 'Libero' WHERE box = ?", (prenotazione[6],))
                conn.commit()

                cursor.execute("SELECT board, port FROM stato_box WHERE box = ?", (box_assegnato,))
                board, port = cursor.fetchone()

                print(f"\nPrenotazione modificata! Il tuo box è stato aggiornato a: {box_assegnato} (board: {board}, port: {port})")
                log_azione(f"Modifica Prenotazione: PIN={pin}, Email={email}, Nuovo Box={box_assegnato}, Nuova Data Inizio={data_inizio}, Nuova Data Fine={data_fine}")
        else:
            print("Nessuna prenotazione trovata con il PIN e l'email forniti.")
    except sqlite3.Error as e:
        print(f"Errore nel database: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Errore: {e}")

def log_azione(azione):
    with open("smart_locker_log.txt", "a") as log_file:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"{timestamp} - {azione}\n")

while True:
    cursor.execute("SELECT pin, box FROM prenotazioni WHERE data_fine < ?", (datetime.datetime.now().isoformat(),))
    for pin, box in cursor.fetchall():
        print(f"\nLa prenotazione {pin} è scaduta!")
        cursor.execute("DELETE FROM prenotazioni WHERE pin = ?", (pin,))
        cursor.execute("UPDATE stato_box SET stato = 'Libero' WHERE box = ?", (box,))
        conn.commit()
        log_azione(f"Prenotazione Scaduta: PIN={pin}, Box={box}")

    # Ottieni l'oggetto datetime corrente
    now = datetime.datetime.now()
    # Formatta la data e l'ora come una stringa
    formatted_datetime = now.strftime("%Y-%m-%d %H:%M:%S")
    # Stampa la data e l'ora formattate
    print("Data e ora correnti: ", formatted_datetime)
    print("\nScegli un'azione: ")
    print("1. Prenota un box")
    print("2. Deposita oggetto")
    print("3. Ritira oggetto")
    print("4. Visualizza box liberi")
    print("5. Visualizza box prenotati e con deposito")

    cursor.execute("SELECT COUNT(*) FROM prenotazioni")
    if cursor.fetchone()[0] > 0:
        print("6. Gestisci prenotazione")

    print("7. Esci")

    scelta = input("> ")
    if scelta == '1':
        prenota_box()
    elif scelta == '2':
        deposita_oggetto()
    elif scelta == '3':
        ritira_oggetto()
    elif scelta == '4':
        mostra_box_liberi()
    elif scelta == '5':
        visualizza_box_prenotati_deposito()
    elif scelta == '6':
        cursor.execute("SELECT COUNT(*) FROM prenotazioni")
        if cursor.fetchone()[0] > 0:
            gestisci_prenotazione()
        else:
            print("Nessuna prenotazione da gestire.")
    elif scelta == '7':
        break
    else:
        print("Scelta non valida.")

conn.close()
