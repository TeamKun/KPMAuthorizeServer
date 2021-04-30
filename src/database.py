import mysql.connector


def genQuery(table, data=[]):
    query = "SELECT * FROM " + table + " "

    leng = len(data)
    if leng != 0:
        query = query + "WHERE "

    for i in range(0, leng):
        query = query + data[i][0] + "= ?"
        if i < leng - 1:
            query = query + " AND "
    return query


class DataBase:

    def __init__(self, host, port, user, pwd, db):
        config = {
            'user': user,
            'password': pwd,
            'host': host,
            'port': port,
            'database': db
        }
        self.connection = mysql.connector.connect(**config)

    def execute(self, query, data=None):
        if data is not None:
            with self.connection.cursor(prepared=True) as cu:
                cu.execute(query, data)
        else:
            with self.connection.cursor() as cu:
                cu.execute(query)
        self.connection.commit()

    def getAll(self, table, data=[]):
        query = genQuery(table, data)

        if len(data) is not 0:
            array = []
            for d in data:
                array.append(d[1])
            with self.connection.cursor(prepared=True) as cu:
                cu.execute(query, array)
                return cu.fetchall()
        else:
            with self.connection.cursor() as cu:
                cu.execute(query)
                return cu.fetchall()

    def getOne(self, table, data=[]):
        query = genQuery(table, data)
        if len(data) is not 0:
            array = []
            for d in data:
                array.append(d[1])
            with self.connection.cursor(prepared=True) as cu:
                cu.execute(query, array)
                return cu.fetchone()
        else:
            with self.connection.cursor() as cu:
                cu.execute(query)
                return cu.fetchone()

    def count(self, table, data=[]):

        query = "SELECT count(*) FROM " + table + " "

        leng = len(data)
        if leng != 0:
            query = query + "WHERE "

        for i in range(0, leng):
            query = query + data[i][0] + "= ?"
            if i < leng - 1:
                query = query + "AND "

        if len(data) is not 0:
            array = []
            for d in data:
                array.append(d[1])
            with self.connection.cursor(prepared=True) as cu:
                cu.execute(query, array)
                return cu.fetchone()[0]
        else:
            with self.connection.cursor() as cu:
                cu.execute(query)
                return cu.fetchone()[0]
