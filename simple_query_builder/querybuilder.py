"""
:authors: co0lc0der
:license: MIT
:copyright: (c) 2022 co0lc0der
"""

import sqlite3
import traceback
import sys
import inspect
from typing import Union


class MetaSingleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class DataBase(metaclass=MetaSingleton):
    db_name = 'db.db'
    conn = None
    cursor = None

    def connect(self, db_name=''):
        if db_name != '':
            self.db_name = db_name

        if self.conn is None:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()

        return self.conn

    def c(self):
        return self.cursor


class QueryBuilder:
    _OPERATORS: list = ['=', '>', '<', '>=', '<=', '!=', 'LIKE', 'NOT LIKE', 'IN', 'NOT IN']
    _LOGICS: list = ['AND', 'OR', 'NOT']
    _SORT_TYPES: list = ['ASC', 'DESC']
    _JOIN_TYPES: list = ['INNER', 'LEFT OUTER', 'RIGHT OUTER', 'FULL OUTER', 'CROSS']
    _NO_FETCH: int = 0
    _FETCH_ONE: int = 1
    _FETCH_ALL: int = 2
    _FETCH_COLUMN: int = 3
    _conn = None
    _cur = None
    _query = None
    _sql: str = ''
    _error: bool = False
    _error_message: str = ''
    _result: Union[tuple, list] = []
    _count: int = -1
    _params: tuple = ()

    def __init__(self, database: DataBase, db_name='') -> None:
        self._conn = database.connect(db_name)
        # self._conn.row_factory = sqlite3.Row
        # self._conn.row_factory = lambda c, r: dict([(col[0], r[idx]) for idx, col in enumerate(c.description)])
        self._cur = database.c()

    def query(self, sql: str = '', params=(), fetch=2, column=0):
        if fetch == 2:
            fetch = self._FETCH_ALL

        self.set_error()

        if sql:
            self._sql = sql

        self.add_semicolon()
        self._sql = self._sql.replace("'NULL'", "NULL")

        if params:
            self._params = params

        try:
            self._query = self._cur.execute(self._sql, self._params)

            if fetch == self._NO_FETCH:
                self._conn.commit()
            elif fetch == self._FETCH_ONE:
                self._result = self._query.fetchone()
            elif fetch == self._FETCH_ALL:
                self._result = self._query.fetchall()
            elif fetch == self._FETCH_COLUMN:
                self._result = [x[column] for x in self._query.fetchall()]

            if self._result:
                self._count = len(self._result)

            self.set_error()
        except sqlite3.Error as er:
            self._error = True
            print('SQLite error: %s' % (' '.join(er.args)))
            print("Exception class is: ", er.__class__)
            print('SQLite traceback: ')
            exc_type, exc_value, exc_tb = sys.exc_info()
            print(traceback.format_exception(exc_type, exc_value, exc_tb))

        return self

    def add_semicolon(self, sql: str = '') -> str:
        new_sql = self._sql if sql == '' else sql

        if new_sql != '':
            new_sql += ';' if new_sql[-1] != ';' else ''

        if sql == '':
            self._sql = new_sql

        return new_sql

    def get_sql(self) -> str:
        return self._sql

    def get_error(self) -> bool:
        return self._error

    def get_error_message(self) -> str:
        return self._error_message

    def set_error(self, message: str = '') -> None:
        self._error = message != ''
        self._error_message = message

    def get_params(self) -> tuple:
        return self._params

    def get_result(self) -> Union[tuple, list]:
        return self._result

    def get_count(self) -> int:
        return self._count

    def reset(self) -> None:
        self._sql = ''
        self._params = ()
        self._query = None
        self._result = []
        self._count = -1
        self.set_error()

    def all(self) -> Union[list, dict]:
        self.query()
        return self._result

    def one(self) -> Union[list, dict]:
        self.query(self._sql, self._params, self._FETCH_ONE)
        return self._result

    def go(self) -> Union[int, None]:
        self.query(self._sql, self._params, self._NO_FETCH)
        return self._cur.lastrowid

    def column(self, column=0):
        self.query('', (), self._FETCH_COLUMN, column)
        return self._result

    def count(self, table: Union[str, dict], field: str = ''):
        if table == '' or table == {}:
            self.set_error(f"Empty table in {inspect.stack()[0][3]} method")
            return self

        if field == '':
            self.select(table, "COUNT(*) AS `counter`")
        else:
            field = field.replace('.', '`.`')
            self.select(table, f"COUNT(`{field}`) AS `counter`")

        return self.one()[0]

    def get_first(self):
        return self.one()

    def get_last(self):
        self.all()
        return self._result[-1]

    def exists(self) -> bool:
        result = self.one()
        return self._count > 0

    def _prepare_aliases(self, items: Union[str, list, dict], as_list: bool = False) -> Union[str, list]:
        if items == '' or items == {} or items == []:
            self.set_error(f"Empty items in {inspect.stack()[0][3]} method")
            return ''

        sql = []
        if isinstance(items, str):
            sql.append(items)
        elif isinstance(items, list) or isinstance(items, dict):
            for item in items:
                if isinstance(items, list):
                    if isinstance(item, str):
                        new_item = item.replace('.', '`.`')
                        sql.append(f"`{new_item}`")
                    elif isinstance(item, dict):
                        first_item = list(item.values())[0].replace('.', '`.`')
                        alias = list(item.keys())[0]
                        if first_item.find('(') > -1 or first_item.find(')') > -1:
                            sql.append(f"{first_item}" if isinstance(alias, int) else f"{first_item} AS `{alias}`")
                        else:
                            sql.append(f"`{first_item}`" if isinstance(alias, int) else f"`{first_item}` AS `{alias}`")
                elif isinstance(items, dict):
                    new_item = items[item].replace('.', '`.`')
                    if new_item.find('(') > -1 or new_item.find(')') > -1:
                        sql.append(f"{new_item}" if isinstance(item, int) else f"{new_item} AS `{item}`")
                    else:
                        sql.append(f"`{new_item}`" if isinstance(item, int) else f"`{new_item}` AS `{item}`")
        else:
            self.set_error(f"Incorrect type of items in {inspect.stack()[0][3]} method")
            return ''

        return ', '.join(sql) if not as_list else sql

    def _prepare_conditions(self, where: Union[str, list]) -> dict:
        result = {'sql': '', 'values': []}
        sql = ''

        if not where:
            return result

        if isinstance(where, str):
            sql += f"{where}"
        elif isinstance(where, list):
            for cond in where:
                if isinstance(cond, list):
                    if len(cond) == 3:
                        field = cond[0].replace('.', '`.`')
                        operator = cond[1].upper()
                        value = cond[2]
                        if operator in self._OPERATORS:
                            if operator == 'IN' and (isinstance(value, list) or isinstance(value, tuple)):
                                values = ("?," * len(value)).rstrip(',')
                                sql += f"(`{field}` {operator} ({values}))"
                                for item in value:
                                    result['values'].append(item)
                            else:
                                sql += f"({field} {operator} ?)" if field.find('(') > -1 or field.find(')') > -1 else f"(`{field}` {operator} ?)"
                                result['values'].append(value)
                elif isinstance(cond, str):
                    upper = cond.upper()
                    if upper in self._LOGICS:
                        sql += f" {upper} "
        else:
            self.set_error(f"Incorrect type of where in {inspect.stack()[0][3]} method")
            return result

        result['sql'] = sql

        return result

    def select(self, table: Union[str, dict], fields: Union[str, list, dict] = '*'):
        if table == '' or table == {} or fields == '' or fields == [] or fields == {}:
            self.set_error(f"Empty table or fields in {inspect.stack()[0][3]} method")
            return self

        self.reset()

        if isinstance(fields, dict) or isinstance(fields, list):
            self._sql = f"SELECT {self._prepare_aliases(fields)}"
        elif isinstance(fields, str):
            self._sql = f"SELECT {fields}"
        else:
            self.set_error(f"Incorrect type of fields in {inspect.stack()[0][3]} method. Fields must be String, List or Dictionary")
            return self

        if isinstance(table, dict):
            self._sql += f" FROM {self._prepare_aliases(table)}"
        elif isinstance(table, str):
            self._sql += f" FROM `{table}`"
        else:
            self.set_error(f"Incorrect type of table in {inspect.stack()[0][3]} method. Table must be String or Dictionary")
            return self

        return self

    def where(self, where: Union[str, list], addition: str = ''):
        if where == '' or where == []:
            self.set_error(f"Empty where in {inspect.stack()[0][3]} method")
            return self

        conditions = self._prepare_conditions(where)

        if addition != '':
            self._sql += f" WHERE {conditions['sql']} {addition}"
        else:
            self._sql += f" WHERE {conditions['sql']}"

        if isinstance(conditions['values'], list) and conditions['values'] != []:
            self._params += tuple(conditions['values'])

        return self

    def having(self, having: Union[str, list]):
        if having == '' or having == []:
            self.set_error(f"Empty having in {inspect.stack()[0][3]} method")
            return self

        conditions = self._prepare_conditions(having)

        self._sql += f" HAVING {conditions['sql']}"

        if isinstance(conditions['values'], list) and conditions['values'] != []:
            self._params += tuple(conditions['values'])

        return self

    def like(self, cond: Union[str, tuple, list] = ()):
        if cond:
            if isinstance(cond, str):
                self.where(cond)
            elif isinstance(cond, tuple) or isinstance(cond, list):
                self.where([[cond[0], 'LIKE', cond[1]]])
        return self

    def not_like(self, cond: Union[str, tuple, list] = ()):
        if cond:
            if isinstance(cond, str):
                self.where(cond)
            elif isinstance(cond, tuple) or isinstance(cond, list):
                self.where([[cond[0], 'NOT LIKE', cond[1]]])
        return self

    def limit(self, limit: int = 1):
        self._sql += f" LIMIT {limit}"
        return self

    def offset(self, offset: int = 0):
        self._sql += f" OFFSET {offset}"
        return self

    def _prepare_sorting(self, field: str = '', sort: str = '') -> tuple:
        if field.find(' ') > -1:
            splitted = field.split(' ')
            field = splitted[0]
            sort = splitted[1]

        field = field.replace('.', '`.`')

        if sort == '':
            sort = 'ASC'
        else:
            sort = sort.upper()

        return f"`{field}`", sort

    def order_by(self, field: Union[str, tuple, list] = (), sort: str = ''):
        if field == '' or field == () or field == []:
            self.set_error(f"Empty field in {inspect.stack()[0][3]} method")
            return self

        if isinstance(field, str):
            field, sort = self._prepare_sorting(field, sort)

            if sort in self._SORT_TYPES:
                self._sql += f" ORDER BY {field} {sort}"
            else:
                self._sql += f" ORDER BY {field}"
        elif isinstance(field, tuple) or isinstance(field, list):
            new_list = [f"{self._prepare_sorting(item)[0]} {self._prepare_sorting(item)[1]}" for item in field]
            self._sql += ' ORDER BY ' + ', '.join(new_list)

        return self

    def group_by(self, field: str = ''):
        if field == '':
            self.set_error(f"Empty field in {inspect.stack()[0][3]} method")
            return self

        field = field.replace('.', '`.`')
        self._sql += f" GROUP BY `{field}`"
        return self

    def delete(self, table: Union[str, dict]):
        if table == '' or table == {}:
            self.set_error(f"Empty table in {inspect.stack()[0][3]} method")
            return self

        if isinstance(table, dict):
            table = f"`{self._prepare_aliases(table)}`"
        elif isinstance(table, str):
            table = f"`{table}`"
        else:
            self.set_error(f"Incorrect type of table in {inspect.stack()[0][3]} method. Table must be String or Dictionary")
            return self

        self.reset()

        self._sql = f"DELETE FROM {table}"
        return self

    def insert(self, table: Union[str, dict], fields: Union[list, dict]):
        if table == '' or table == {} or fields == [] or fields == {}:
            self.set_error(f"Empty table or fields in {inspect.stack()[0][3]} method")
            return self

        if isinstance(table, dict):
            table = f"`{self._prepare_aliases(table)}`"
        elif isinstance(table, str):
            table = f"`{table}`"
        else:
            self.set_error(f"Incorrect type of table in {inspect.stack()[0][3]} method. Table must be String or Dictionary")
            return self

        self.reset()

        if isinstance(fields, dict):
            values = ("?," * len(fields)).rstrip(',')
            self._sql = f"INSERT INTO {table} (`" + '`, `'.join(list(fields.keys())) + f"`) VALUES ({values})"
            self._params = tuple(fields.values())
        elif isinstance(fields, list):
            names = fields.pop(0)
            value = ("?," * len(names)).rstrip(',')
            v = f"({value}),"
            values = (v * len(fields)).rstrip(',')
            self._sql = f"INSERT INTO {table} (`" + '`, `'.join(names) + f"`) VALUES {values}"
            params = []
            for item in fields:
                if isinstance(item, list):
                    for subitem in item:
                        params.append(subitem)
            self._params = tuple(params)
        else:
            self.set_error(f"Incorrect type of fields in {inspect.stack()[0][3]} method. Fields must be String, List or Dictionary")
            return self

        return self

    def update(self, table: Union[str, dict], fields: Union[list, dict]):
        if table == '' or table == {} or fields == [] or fields == {}:
            self.set_error(f"Empty table or fields in {inspect.stack()[0][3]} method")
            return self

        if isinstance(table, dict):
            table = f"`{self._prepare_aliases(table)}`"
        elif isinstance(table, str):
            table = f"`{table}`"
        else:
            self.set_error(f"Incorrect type of table in {inspect.stack()[0][3]} method. Table must be String or Dictionary")
            return self

        if isinstance(fields, list) or isinstance(fields, dict):
            sets = ''
            for item in fields:
                sets += f" `{item.replace('.', '`.`')}` = ?,"
            sets = sets.rstrip(',')
        else:
            self.set_error(f"Incorrect type of fields in {inspect.stack()[0][3]} method. Fields must be String, List or Dictionary")
            return self

        self.reset()

        self._sql = f"UPDATE {table} SET{sets}"
        self._params = tuple(fields.values())

        return self

    def join(self, table: Union[str, dict] = '', on: Union[str, tuple, list] = (), join_type: str = 'INNER'):
        join_type = join_type.upper()
        if join_type == '' or join_type not in self._JOIN_TYPES:
            self.set_error(f"Empty join_type or is not allowed in {inspect.stack()[0][3]} method")
            return self

        if table == '' or table == {}:
            self.set_error(f"Empty table in {inspect.stack()[0][3]} method")
            return self

        if isinstance(table, dict):
            self._sql += f" {join_type} JOIN {self._prepare_aliases(table)}"
        elif isinstance(table, str):
            self._sql += f" {join_type} JOIN `{table}`"
        else:
            self.set_error(f"Incorrect type of table in {inspect.stack()[0][3]} method. Table must be String or Dictionary")
            return self

        if on:
            if isinstance(on, tuple) or isinstance(on, list):
                field1 = f"`{on[0].replace('.', '`.`')}`"
                field2 = f"`{on[1].replace('.', '`.`')}`"
                self._sql += f" ON {field1} = {field2}"
            elif isinstance(on, str):
                self._sql += f" ON {on}"
            else:
                self.set_error(f"Incorrect type of on in {inspect.stack()[0][3]} method. On must be String, Tuple or List")
                return self

        self.set_error()

        return self

    def drop(self, table: str, add_exists: bool = True):
        if table == '':
            self.set_error(f"Empty table in {inspect.stack()[0][3]} method")
            return self

        exists = 'IF EXISTS ' if add_exists else ''

        self.reset()
        self._sql = f"DROP TABLE {exists}`{table}`"

        return self

    def truncate(self, table: str):
        if table == '':
            self.set_error(f"Empty table in {inspect.stack()[0][3]} method")
            return self

        self.reset()
        self._sql = f"TRUNCATE TABLE `{table}`"

        return self
